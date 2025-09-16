#!/usr/bin/env bash

set -euo pipefail

# Restore PostgreSQL database from a dump (custom/SQL). Optionally handle SQLite dump detection.
#
# Usage:
#   ./scripts/restore_database.sh /path/to/dump [--no-migrate]
#
# Behavior:
# - Detects dump type: PostgreSQL custom (-Fc), plain SQL, or SQLite file
# - Works with native Postgres or docker-compose stack (service name: db)
# - Stops app containers during restore, creates timestamped backup, terminates connections,
#   drops and recreates the DB, restores, runs Django migrations, VACUUM ANALYZE
#
# Requirements (native): psql, pg_dump, pg_restore (for custom dumps)
# Requirements (docker): docker compose (or docker-compose)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

COLOR_RED='\033[0;31m'
COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[0;33m'
COLOR_RESET='\033[0m'

log() { echo -e "${COLOR_GREEN}[restore]${COLOR_RESET} $*"; }
warn() { echo -e "${COLOR_YELLOW}[restore]${COLOR_RESET} $*"; }
err() { echo -e "${COLOR_RED}[restore]${COLOR_RESET} $*" 1>&2; }

if [[ $# -lt 1 ]]; then
  err "Укажите путь к файлу дампа."
  echo "Пример: $0 ~/Desktop/expense_prod.dump"
  exit 1
fi

DUMP_PATH="$1"
shift || true
RUN_MIGRATIONS=true
if [[ "${1:-}" == "--no-migrate" ]]; then
  RUN_MIGRATIONS=false
  shift || true
fi

if [[ ! -f "$DUMP_PATH" ]]; then
  err "Файл дампа не найден: $DUMP_PATH"
  exit 1
fi

# Load .env if present
if [[ -f "$PROJECT_ROOT/.env" ]]; then
  # shellcheck disable=SC1091
  source "$PROJECT_ROOT/.env"
fi

# Defaults
DB_NAME="${DB_NAME:-expense_bot}"
DB_USER="${DB_USER:-expense_user}"
DB_PASSWORD="${DB_PASSWORD:-}" # may be empty if using peer/local auth or docker env
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"

# Detect docker compose availability and service
DOCKER_COMPOSE_BIN=""
if command -v docker &>/dev/null; then
  if docker compose version &>/dev/null; then
    DOCKER_COMPOSE_BIN="docker compose"
  elif command -v docker-compose &>/dev/null; then
    DOCKER_COMPOSE_BIN="docker-compose"
  fi
fi

IN_DOCKER_STACK=false
DB_SERVICE="db"
WEB_SERVICE="web"
BOT_SERVICE="bot"
CELERY_SERVICE="celery"
CELERY_BEAT_SERVICE="celery-beat"

if [[ -n "$DOCKER_COMPOSE_BIN" ]] && [[ -f "$PROJECT_ROOT/docker-compose.prod.yml" || -f "$PROJECT_ROOT/docker-compose.yml" ]]; then
  # Try to see if DB container exists or stack is up
  if $DOCKER_COMPOSE_BIN ps --services 2>/dev/null | grep -q "^${DB_SERVICE}$"; then
    IN_DOCKER_STACK=true
    log "Обнаружен docker-compose стек. Будет использоваться восстановление через контейнер ${DB_SERVICE}."
  fi
fi

detect_dump_type() {
  local file="$1"
  local ext="${file##*.}"
  case "$ext" in
    dump|backup|custom)
      echo "pg_custom"
      return 0
      ;;
    sql)
      echo "sql"
      return 0
      ;;
    db|sqlite|sqlite3)
      echo "sqlite"
      return 0
      ;;
    gz|tgz)
      # Try to detect inside
      if zcat "$file" 2>/dev/null | head -c 64 | grep -qi "PostgreSQL"; then
        echo "sql_gz"
        return 0
      fi
      ;;
  esac
  # Fallback to file command
  if command -v file &>/dev/null; then
    local ft
    ft="$(file -b "$file" || true)"
    if echo "$ft" | grep -qi "PostgreSQL custom database dump"; then
      echo "pg_custom"; return 0
    fi
    if echo "$ft" | grep -qi "SQLite"; then
      echo "sqlite"; return 0
    fi
    if echo "$ft" | grep -qi "ASCII text\|UTF-8 text"; then
      echo "sql"; return 0
    fi
  fi
  # Last resort: peek into content
  if head -c 16 "$file" | grep -q "PGDMP"; then
    echo "pg_custom"; return 0
  fi
  echo "unknown"
}

DUMP_TYPE="$(detect_dump_type "$DUMP_PATH")"
log "Тип дампа: $DUMP_TYPE"

if [[ "$DUMP_TYPE" == "sqlite" ]]; then
  err "Вы передали SQLite-базу (.$(echo "$DUMP_PATH" | awk -F. '{print $NF}')). Для продакшена у нас PostgreSQL.\n"
  err "Варианты: 1) Использовать pgloader для миграции SQLite → PostgreSQL, 2) Подать SQL дамп PostgreSQL."
  echo "Подсказка для pgloader (на сервере):"
  echo "  pgloader sqlite:///$DUMP_PATH postgresql://$DB_USER:${DB_PASSWORD:-password}@${DB_HOST}:${DB_PORT}/$DB_NAME"
  exit 2
fi

confirm() {
  read -r -p "Продолжить восстановление базы '$DB_NAME' из '$DUMP_PATH'? [y/N]: " ans || true
  [[ "$ans" == "y" || "$ans" == "Y" ]]
}

if ! confirm; then
  err "Операция отменена пользователем."
  exit 1
fi

# Stop app to release connections
stop_app() {
  if $IN_DOCKER_STACK; then
    warn "Останавливаю контейнеры приложения (web, bot, celery, celery-beat)"
    $DOCKER_COMPOSE_BIN stop "$WEB_SERVICE" "$BOT_SERVICE" "$CELERY_SERVICE" "$CELERY_BEAT_SERVICE" >/dev/null || true
  else
    warn "Пропускаю остановку приложения (не docker). Убедитесь, что сервисы не держат соединения."
  fi
}

start_app() {
  if $IN_DOCKER_STACK; then
    log "Запускаю контейнеры приложения"
    $DOCKER_COMPOSE_BIN start "$WEB_SERVICE" "$BOT_SERVICE" "$CELERY_SERVICE" "$CELERY_BEAT_SERVICE" >/dev/null || true
  else
    warn "Пропускаю запуск приложения (не docker)"
  fi
}

pg_exec() {
  local cmd=("psql" "-h" "$DB_HOST" "-p" "$DB_PORT" "-U" "$DB_USER" "-d" "$DB_NAME" "-v" "ON_ERROR_STOP=1" -c "$1")
  if $IN_DOCKER_STACK; then
    # Run inside db container; -U uses POSTGRES_USER inside container; override with -U
    $DOCKER_COMPOSE_BIN exec -T "$DB_SERVICE" sh -lc "PGPASSWORD=\"$DB_PASSWORD\" ${cmd[*]}"
  else
    PGPASSWORD="$DB_PASSWORD" "${cmd[@]}"
  fi
}

pg_run_file() {
  local file="$1"
  if $IN_DOCKER_STACK; then
    # Copy file into container and run
    local tmp="/tmp/restore_$(date +%s).sql"
    docker cp "$file" "$( $DOCKER_COMPOSE_BIN ps -q "$DB_SERVICE" ):$tmp"
    $DOCKER_COMPOSE_BIN exec -T "$DB_SERVICE" sh -lc "PGPASSWORD=\"$DB_PASSWORD\" psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -v ON_ERROR_STOP=1 -f $tmp"
    $DOCKER_COMPOSE_BIN exec -T "$DB_SERVICE" rm -f "$tmp" || true
  else
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -f "$file"
  fi
}

pg_dump_backup() {
  local backup_file="$PROJECT_ROOT/backup_${DB_NAME}_$(date +%Y%m%d_%H%M%S).dump"
  log "Создаю резервную копию текущей БД: $backup_file"
  if $IN_DOCKER_STACK; then
    $DOCKER_COMPOSE_BIN exec -T "$DB_SERVICE" sh -lc "PGPASSWORD=\"$DB_PASSWORD\" pg_dump -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -Fc -f /tmp/backup.dump"
    docker cp "$( $DOCKER_COMPOSE_BIN ps -q "$DB_SERVICE" ):/tmp/backup.dump" "$backup_file"
    $DOCKER_COMPOSE_BIN exec -T "$DB_SERVICE" rm -f /tmp/backup.dump || true
  else
    PGPASSWORD="$DB_PASSWORD" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -Fc -f "$backup_file"
  fi
  log "Бэкап создан."
}

terminate_connections() {
  warn "Завершаю активные подключения к БД $DB_NAME"
  local sql="SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$DB_NAME' AND pid <> pg_backend_pid();"
  pg_exec "$sql" || true
}

drop_and_create_db() {
  warn "Пересоздаю базу данных $DB_NAME"
  local drop="DROP DATABASE IF EXISTS \"$DB_NAME\";"
  local create="CREATE DATABASE \"$DB_NAME\" OWNER \"$DB_USER\";"
  # Need to connect to postgres db for drop/create
  if $IN_DOCKER_STACK; then
    $DOCKER_COMPOSE_BIN exec -T "$DB_SERVICE" sh -lc "PGPASSWORD=\"$DB_PASSWORD\" psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -v ON_ERROR_STOP=1 -c \"$drop\" -c \"$create\""
  else
    PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1 -c "$drop" -c "$create"
  fi
}

restore_custom() {
  log "Восстанавливаю из custom дампа (pg_restore)"
  if $IN_DOCKER_STACK; then
    local tmp="/tmp/restore_$(date +%s).dump"
    docker cp "$DUMP_PATH" "$( $DOCKER_COMPOSE_BIN ps -q "$DB_SERVICE" ):$tmp"
    $DOCKER_COMPOSE_BIN exec -T "$DB_SERVICE" sh -lc "PGPASSWORD=\"$DB_PASSWORD\" pg_restore -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -c -j 4 $tmp"
    $DOCKER_COMPOSE_BIN exec -T "$DB_SERVICE" rm -f "$tmp" || true
  else
    PGPASSWORD="$DB_PASSWORD" pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c -j 4 "$DUMP_PATH"
  fi
}

restore_sql() {
  log "Восстанавливаю из SQL дампа (psql -f)"
  pg_run_file "$DUMP_PATH"
}

post_restore() {
  log "VACUUM ANALYZE…"
  if $IN_DOCKER_STACK; then
    $DOCKER_COMPOSE_BIN exec -T "$DB_SERVICE" sh -lc "PGPASSWORD=\"$DB_PASSWORD\" vacuumdb -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -z" || true
  else
    PGPASSWORD="$DB_PASSWORD" vacuumdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -z || true
  fi

  if $RUN_MIGRATIONS; then
    log "Выполняю Django миграции"
    if $IN_DOCKER_STACK; then
      $DOCKER_COMPOSE_BIN run --rm "$WEB_SERVICE" python manage.py migrate --noinput
    else
      (cd "$PROJECT_ROOT" && python3 manage.py migrate --noinput)
    fi
  else
    warn "Пропускаю Django миграции по флагу --no-migrate"
  fi
}

main() {
  stop_app
  pg_dump_backup
  terminate_connections
  drop_and_create_db
  case "$DUMP_TYPE" in
    pg_custom) restore_custom ;;
    sql) restore_sql ;;
    sql_gz)
      log "Разархивирую и загружаю SQL дамп"
      if $IN_DOCKER_STACK; then
        local tmp="/tmp/restore_$(date +%s).sql"
        # copy gz, unzip inside container then psql
        local tmpgz="${tmp}.gz"
        docker cp "$DUMP_PATH" "$( $DOCKER_COMPOSE_BIN ps -q "$DB_SERVICE" ):$tmpgz"
        $DOCKER_COMPOSE_BIN exec -T "$DB_SERVICE" sh -lc "gunzip -c $tmpgz > $tmp && rm -f $tmpgz && PGPASSWORD=\"$DB_PASSWORD\" psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -v ON_ERROR_STOP=1 -f $tmp && rm -f $tmp"
      else
        zcat "$DUMP_PATH" | PGPASSWORD="$DB_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1
      fi
      ;;
    *)
      err "Неизвестный тип дампа. Поддерживаются: .dump/.backup (pg_restore), .sql, .sql.gz"
      start_app
      exit 3
      ;;
  esac
  post_restore
  start_app
  log "Готово. База данных восстановлена из: $DUMP_PATH"
}

main "$@"

