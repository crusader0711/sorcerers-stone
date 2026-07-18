# Static assets — vendor libraries served locally (no CDN)
#
# These files need to be downloaded once and committed.
# REQ-DASH-3 / INV-1: No external resource requests from the browser.
#
# Download instructions:
#   Tailwind CSS (standalone CLI build):
#     npx tailwindcss -i app/static/css/app.css -o app/static/css/tailwind.min.css --minify
#     OR download pre-built: https://cdn.tailwindcss.com/ (save locally)
#
#   HTMX:
#     curl -o app/static/js/htmx.min.js https://unpkg.com/htmx.org@2.0.4/dist/htmx.min.js
#
#   Chart.js:
#     curl -o app/static/js/chart.min.js https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js
#
# After downloading, these files are committed to git — zero runtime CDN calls.
