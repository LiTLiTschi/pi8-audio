# Sourced from ~/.profile — only on the physical text console (VT1).
# Shows a rolling status dashboard; Ctrl+C exits to a normal login shell.

case "$(tty 2>/dev/null)" in
  /dev/tty1)
    if [ -x "${HOME}/bin/pi8-tty-dash" ]; then
      "${HOME}/bin/pi8-tty-dash"
    fi
    ;;
esac
