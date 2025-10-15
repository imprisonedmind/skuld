#!/usr/bin/env bash
set -euo pipefail

# Scaffolds a Homebrew tap repo for Skuld.
# Usage:
#   scripts/scaffold_tap.sh [owner=imprisonedmind] [name=homebrew-skuld] [tag=v0.1.0] [sha256=<tarball sha>]
# If tag+sha256 are omitted, the formula will be HEAD-only; you can add a stable URL later.

OWNER=${1:-imprisonedmind}
NAME=${2:-homebrew-skuld}
TAG=${3:-}
SHA=${4:-}

WORKDIR=$(mktemp -d)
TAP_DIR="$WORKDIR/$NAME"
mkdir -p "$TAP_DIR/Formula"

cat > "$TAP_DIR/Formula/skuld.rb" <<'RUBY'
class Skuld < Formula
  desc "Skuld: WakaTime + Git → Jira worklogs"
  homepage "https://github.com/imprisonedmind/skuld"
RUBY

if [[ -n "$TAG" && -n "$SHA" ]]; then
  cat >> "$TAP_DIR/Formula/skuld.rb" <<RUBY
  url "https://github.com/imprisonedmind/skuld/archive/refs/tags/$TAG.tar.gz"
  sha256 "$SHA"
  license :cannot_represent
RUBY
fi

cat >> "$TAP_DIR/Formula/skuld.rb" <<'RUBY'
  head "https://github.com/imprisonedmind/skuld.git", branch: "main"

  depends_on "python"

  def install
    libexec.install Dir["skuld", "docs", ".skuld.yaml.example", "README.md", "LICENSE"]
    (bin/"skuld").write <<~EOS
      #!/bin/bash
      export PYTHONPATH="#{libexec}"
      exec "#{Formula["python"].opt_bin}/python3" -m skuld.cli "$@"
    EOS
    (bin/"skuld").chmod 0755
  end

  test do
    system "#{bin}/skuld", "sync", "today", "--test"
  end
end
RUBY

pushd "$TAP_DIR" >/dev/null
git init -q
git add .
git commit -m "Skuld tap: add formula" >/dev/null

echo "---"
echo "Tap repo scaffolded at: $TAP_DIR"
echo "Next steps:"
echo "1) Create GitHub repo: https://github.com/new (owner: $OWNER, name: $NAME)"
echo "2) cd $TAP_DIR && git remote add origin https://github.com/$OWNER/$NAME.git && git branch -M main && git push -u origin main"
echo "3) On client machines: brew tap $OWNER/skuld && brew install skuld"
popd >/dev/null
