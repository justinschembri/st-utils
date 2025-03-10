from sensorthings_utils import netatmo


def stream_all() -> None:
    netatmo.stream()


if __name__ == "__main__":
    while True:
        print("Application being called!")
        # stream_all()
