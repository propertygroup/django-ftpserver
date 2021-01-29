import argparse
import subprocess


def stress_test(
    login: str, password: str, url: str, port: int, infinite: str = "F"
) -> None:
    subprocess_text = ""
    for item in range(int(args.cores)):
        subprocess_text += (
            f"python3 benchmark.py --login {login} --password {password} "
            f"--url {url} --port {port} --infinite {infinite} & "
        )
    subprocess_text = subprocess_text[:-2]
    subprocess.run(subprocess_text, shell=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--login", default="test")
    parser.add_argument("--password", default="Test123!")
    parser.add_argument("--url", default="127.0.0.1")
    parser.add_argument("--port", default=10021, type=int)
    parser.add_argument("--cores", default=50, type=int)
    parser.add_argument("--infinite", default="F", help="Infinite loop T/F?")
    args = parser.parse_args()
    stress_test(args.login, args.password, args.url, args.port, args.infinite)
