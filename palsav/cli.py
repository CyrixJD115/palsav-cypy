import os
import sys


def main():
    if os.environ.get("PYTHONHASHSEED", "random") != "0":
        os.environ["PYTHONHASHSEED"] = "0"
        os.execv(sys.argv[0], sys.argv)

    from palsav.commands.convert import main as convert_main

    convert_main()


if __name__ == "__main__":
    main()
