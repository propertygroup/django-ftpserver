import argparse
import io
import os
import uuid
from ftplib import FTP


# def get_from_list_or_none(data: List[Any]) -> Optional[Any]:


class FTPBenchmark:
    def __init__(
        self, path: str, login: str, password: str, url: str, port: int = 10021
    ) -> None:
        self.file = io.BytesIO(os.urandom(1024))
        self.ftp = FTP()
        self.ftp.connect(host=url, port=port)
        self.ftp.login(user=login, passwd=password)
        self.path = path

    def list_files(self) -> None:
        for item in range(50):
            self.ftp.retrlines(f"LIST {self.path_creator(item)}")

    def send_files(self) -> None:
        for item in range(50):
            self.file.seek(0)
            self.ftp.storbinary(f"STOR {self.path_creator(item)}", self.file)

    def path_creator(self, number: int) -> str:
        return f"{self.path}/file{number}.txt"

    def send_and_check_files_infinite(self) -> None:
        i = 0
        while True:
            self.file.seek(0)
            file_path = self.path_creator(i)
            self.ftp.storbinary(f"STOR {file_path}", self.file)
            self.ftp.retrlines(f"LIST {file_path}")
            i += 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--login", default="test")
    parser.add_argument("--password", default="Test123!")
    parser.add_argument("--url", default="127.0.0.1")
    parser.add_argument("--port", default=10021, type=int)
    parser.add_argument("--infinite", default="F", help="Infinite loop T/F?")
    args = parser.parse_args()
    infinite = True if args.infinite == "T" else False
    path = str(uuid.uuid4())
    ftp = FTPBenchmark(path, args.login, args.password, args.url, args.port)
    if args.infinite == "T":
        ftp.send_and_check_files_infinite()
    else:
        ftp.send_files()
        ftp.list_files()
