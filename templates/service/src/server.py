"""Background service."""
import time

def main():
    while True:
        print("service alive")
        time.sleep(60)

if __name__ == "__main__":
    main()
