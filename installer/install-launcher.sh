#!/usr/bin/env bash
# Install a global per-user launcher that runs cyberspace's virtual environment.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="${1:-$(dirname "${SCRIPT_DIR}")}"
BIN_DIR="${CYBERSPACE_BIN_DIR:-${HOME}/.local/bin}"
LAUNCHER="${BIN_DIR}/cyberspace"
ENTRYPOINT="${ROOT_DIR}/.venv/bin/cyberspace"

if [[ ! -x "${ENTRYPOINT}" ]]; then
  printf '[x] cyberspace entry point not found at %s\n' "${ENTRYPOINT}" >&2
  printf '    Repair it: cd "%s" && .venv/bin/pip install -e .\n' "${ROOT_DIR}" >&2
  exit 1
fi

mkdir -p "${BIN_DIR}"
printf -v quoted_root '%q' "${ROOT_DIR}"
printf -v quoted_launcher '%q' "${LAUNCHER}"
tmp="${LAUNCHER}.tmp.$$"
cat >"${tmp}" <<EOF
#!/usr/bin/env bash
set -euo pipefail
# Managed by cyberspace installer.
CYBERSPACE_ROOT=${quoted_root}
export CYBERSPACE_ROOT
export CYBERSPACE_LAUNCHER_PATH=${quoted_launcher}
ENTRYPOINT="\${CYBERSPACE_ROOT}/.venv/bin/cyberspace"
if [[ ! -x "\${ENTRYPOINT}" ]]; then
  printf 'cyberspace: installed entry point is missing at %s\\n' "\${ENTRYPOINT}" >&2
  printf 'Repair it with: cd %q && .venv/bin/pip install -e .\\n' "\${CYBERSPACE_ROOT}" >&2
  exit 127
fi
exec "\${ENTRYPOINT}" "\$@"
EOF
chmod 755 "${tmp}"
mv -f "${tmp}" "${LAUNCHER}"

# Add the launcher directory to future shells only when it is not already available.
if [[ "${CYBERSPACE_SKIP_PATH_UPDATE:-0}" != "1" ]]; then
  case ":${PATH}:" in
    *":${BIN_DIR}:"*) ;;
    *)
    shell_name="$(basename "${SHELL:-sh}")"
    case "${shell_name}" in
      zsh) profile="${HOME}/.zprofile" ;;
      bash) profile="${HOME}/.bash_profile" ;;
      *) profile="${HOME}/.profile" ;;
    esac
    marker="# cyberspace launcher"
    printf -v quoted_bin '%q' "${BIN_DIR}"
    if ! grep -Fq "${marker}" "${profile}" 2>/dev/null; then
      printf '\n%s\nexport PATH=%s:"$PATH"\n' "${marker}" "${quoted_bin}" >>"${profile}"
    fi
    printf '[!] Added %s to PATH in %s; open a new terminal or run:\n' "${BIN_DIR}" "${profile}"
    printf '    export PATH=%s:"$PATH"\n' "${quoted_bin}"
    ;;
  esac
fi

printf '[ok] launcher installed: %s\n' "${LAUNCHER}"
printf '     Run `cyberspace` from any directory; venv activation is automatic.\n'