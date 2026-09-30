"""Патч houdini_mcp_server.py (идемпотентный): запускается из install.ps1.

1. Первый вызов после простоя/падения давал WinError 10053/10054 и требовал повтора вручную:
   теперь при обрыве сокета клиент переподключается и повторяет команду один раз.
2. execute_houdini_code возвращал только "Code executed successfully": теперь отдаёт ответ плагина
   (stdout/результат, если плагин их присылает).
"""
import sys

path = sys.argv[1]
src = open(path, encoding="utf-8").read()
MARK = "# studio-bridge patch"
if MARK in src:
    print("already patched")
    raise SystemExit(0)

old_sig = "    def send_command(self, command_type: str, params: Dict[str, Any] = None) -> Dict[str, Any]:\n"
new_sig = (
    "    def send_command(self, command_type: str, params: Dict[str, Any] = None) -> Dict[str, Any]:\n"
    "        " + MARK + ": one silent reconnect+retry when the socket was dead (WinError 10053/10054)\n"
    "        try:\n"
    "            return self._send_command(command_type, params)\n"
    "        except Exception as exc:\n"
    "            text = str(exc)\n"
    "            if any(k in text for k in ('10053', '10054', '10058', 'lost', 'closed', 'Broken')):\n"
    "                self.sock = None\n"
    "                return self._send_command(command_type, params)\n"
    "            raise\n\n"
    "    def _send_command(self, command_type: str, params: Dict[str, Any] = None) -> Dict[str, Any]:\n"
)
assert old_sig in src, "send_command signature not found"
src = src.replace(old_sig, new_sig, 1)
src = src.replace("return self.send_command(command_type, params)", "return self._send_command(command_type, params)")

old_ret = '        return f"Code executed successfully in Houdini"'
new_ret = (
    "        import json as _json\n"
    "        extra = ''\n"
    "        if isinstance(result, dict):\n"
    "            extra = _json.dumps(result, ensure_ascii=False, default=str)[:6000]\n"
    '        return "Code executed successfully in Houdini" + (": " + extra if extra and extra != "{}" else "")'
)
assert old_ret in src, "execute return not found"
src = src.replace(old_ret, new_ret, 1)
open(path, "w", encoding="utf-8").write(src)
print("patched")
