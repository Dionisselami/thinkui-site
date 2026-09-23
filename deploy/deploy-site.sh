#!/usr/bin/env bash
# Deploy the marketing site to the box.
#
#   bash deploy/deploy-site.sh
#
# Pages and assets only: src/ (the templates), brand/ (the identity toolchain) and the
# local launchers have no business on a web server. The vhost is the one in this folder,
# so the server config cannot drift from what is in git.

set -euo pipefail

HOST="${THINKUI_HOST:-thinkui}"
SITE_DIR="/var/www/thinkui"
REPO="$(cd "$(dirname "$0")/.." && pwd)"

step() { printf '\n\033[1m== %s\033[0m\n' "$1"; }

step "1/4 rebuild the site from src/"
# relative paths, not "$REPO": these run through a native python that cannot open an
# MSYS-style /c/... path
(cd "$REPO" && python src/build.py && python src/audit.py | tail -3)

step "2/4 ship pages and assets"
cd "$REPO"
# no _redirects: that file was for Cloudflare Pages, and the old corpus addresses are
# 301s in the vhost now
tar czf - index.html pricing.html docs.html login.html signup.html terms.html \
         privacy.html 404.html sitemap.xml robots.txt site.webmanifest assets \
  | ssh "$HOST" "sudo tar xzf - -C $SITE_DIR && sudo chown -R www-data:www-data $SITE_DIR"

step "3/4 vhost"
ssh "$HOST" "cat > /tmp/thinkui.conf" < "$REPO/deploy/nginx-thinkui.conf"
ssh "$HOST" "set -e
  sudo mv /tmp/thinkui.conf /etc/nginx/sites-available/thinkui
  sudo /usr/sbin/nginx -t
  sudo systemctl reload nginx
  echo 'nginx reloaded'"

step "4/4 what is actually being served"
ssh "$HOST" "for p in / /pricing /docs /login /signup /terms /privacy /404.html; do
               printf '%-12s %s\n' \"\$p\" \"\$(curl -s -o /dev/null -w 'HTTP %{http_code}  %{size_download} bytes' -k -H 'Host: thinkui.xyz' https://127.0.0.1\$p)\"
             done
             printf '%-12s %s\n' '/assets/css' \"\$(curl -s -o /dev/null -w 'HTTP %{http_code}' -k -H 'Host: thinkui.xyz' https://127.0.0.1/assets/css/site.css)\""

step "done"
