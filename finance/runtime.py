"""Launch finance subcommands from source or the packaged desktop."""
import sys

def command(module, args):
    allowed={"finance.worker":"--worker","finance.browser_pilot":"--browser","finance.office":"--office","finance.operation":"--operation"}
    if module not in allowed:
        raise ValueError("Unsupported finance child process")
    if getattr(sys,"frozen",False):
        return [sys.executable,allowed[module],*args]
    return [sys.executable,"-u","-m",module,*args]
