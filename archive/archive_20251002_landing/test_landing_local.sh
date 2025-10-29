#!/bin/bash
# Local testing server for landing page

cd /mnt/c/Users/_batman_/Desktop/expense_bot/landing

echo "🚀 Starting local test server for landing page..."
echo ""
echo "📂 Serving files from: $(pwd)"
echo ""
echo "🌐 Open in browser:"
echo "   Main page (RU): http://localhost:8080/index.html"
echo "   Main page (EN): http://localhost:8080/index_en.html"
echo "   Privacy (RU):   http://localhost:8080/privacy.html"
echo "   Privacy (EN):   http://localhost:8080/privacy_en.html"
echo "   Offer (RU):     http://localhost:8080/offer.html"
echo "   Offer (EN):     http://localhost:8080/offer_en.html"
echo ""
echo "🔍 To test WebP optimization:"
echo "   1. Open DevTools (F12) → Network tab"
echo "   2. Refresh page (Ctrl+F5)"
echo "   3. Check that .webp images are loaded"
echo "   4. Compare file sizes (should be ~88% smaller)"
echo ""
echo "⏹️  Press Ctrl+C to stop server"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Start Python HTTP server
python3 -m http.server 8080
