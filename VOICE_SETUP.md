# Настройка распознавания голоса

Для работы распознавания голосовых сообщений необходимо:

## 1. Установить Python библиотеки (уже установлены):
```
pip install SpeechRecognition pydub
```

## 2. Установить FFmpeg:

### Windows:
1. Скачайте FFmpeg с https://ffmpeg.org/download.html
2. Распакуйте архив в папку (например, C:\ffmpeg)
3. Добавьте путь к папке bin (C:\ffmpeg\bin) в переменную окружения PATH

### Альтернативный способ для Windows:
```
# Через Chocolatey
choco install ffmpeg

# Или через winget
winget install ffmpeg
```

### Linux:
```
sudo apt update
sudo apt install ffmpeg
```

### macOS:
```
brew install ffmpeg
```

## Проверка установки:
```
ffmpeg -version
```

## Использование:
После установки FFmpeg распознавание голоса будет работать автоматически.
Просто отправьте голосовое сообщение боту, и он распознает текст.