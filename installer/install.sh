#!/usr/bin/env bash
# Install the latest standalone Cyberspace executable on macOS or Linux.
set -euo pipefail

repo="nim2natty/cyberspace"
version="${CYBERSPACE_VERSION:-latest}"
bin_dir="${CYBERSPACE_BIN_DIR:-${HOME}/.local/bin}"
die() { printf '[cyberspace] error: %s\n' "$1" >&2; exit 1; }
command -v curl >/dev/null 2>&1 || die "curl is required"

case "$(uname -s)" in Darwin) os="macos" ;; Linux) os="linux" ;;
  *) die "unsupported OS; Windows users should run installer/install.ps1" ;; esac
case "$(uname -m)" in x86_64|amd64) arch="x86_64" ;; arm64|aarch64) arch="arm64" ;;
  *) die "unsupported CPU architecture: $(uname -m)" ;; esac

asset="cyberspace-${os}-${arch}"
if [[ "${version}" == "latest" ]]; then
  base="https://github.com/${repo}/releases/latest/download"
else
  base="https://github.com/${repo}/releases/download/${version}"
fi
mkdir -p "${bin_dir}"
tmp="$(mktemp "${TMPDIR:-/tmp}/cyberspace.XXXXXX")"
trap 'rm -f "${tmp}" "${tmp}.sha256"' EXIT
printf '[cyberspace] downloading %s...\n' "${asset}"
curl -fL --retry 3 "${base}/${asset}" -o "${tmp}" || die "compatible release not found"
curl -fL --retry 3 "${base}/${asset}.sha256" -o "${tmp}.sha256" || die "checksum missing"
expected="$(awk '{print $1}' "${tmp}.sha256")"
if command -v shasum >/dev/null 2>&1; then
  actual="$(shasum -a 256 "${tmp}" | awk '{print $1}')"
else
  actual="$(sha256sum "${tmp}" | awk '{print $1}')"
fi
[[ "${actual}" == "${expected}" ]] || die "checksum verification failed"
chmod 755 "${tmp}" && mv -f "${tmp}" "${bin_dir}/cyberspace"

case ":${PATH}:" in *":${bin_dir}:"*) ;;
  *)
    case "$(basename "${SHELL:-sh}")" in zsh) profile="${HOME}/.zprofile" ;;
      bash) profile="${HOME}/.bash_profile" ;; *) profile="${HOME}/.profile" ;; esac
    marker="# cyberspace executable"
    grep -Fq "${marker}" "${profile}" 2>/dev/null ||
      printf '\n%s\nexport PATH="%s:$PATH"\n' "${marker}" "${bin_dir}" >>"${profile}"
    printf '[cyberspace] added %s to PATH; open a new terminal.\n' "${bin_dir}" ;;
esac
printf '[cyberspace] installed and verified: %s\n' "${bin_dir}/cyberspace"
printf 'Next: cyberspace setup && cyberspace doctor\n'
