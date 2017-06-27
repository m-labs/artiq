import sys, subprocess

def main():
    exit(not subprocess.call(sys.argv[1:]))

if __name__ == "__main__":
    main()
