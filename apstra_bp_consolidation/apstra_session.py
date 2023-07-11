#!/usr/bin/env python3.11
import requests
import urllib3

# https client session to Apstra Controller
class CkApstraSession:

    def __init__(self, host: str, port: int, username: str, password: str) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.token = None
        self.ssl_verify = False

        self.session = requests.Session()
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.session.verify = False
        self.session.headers.update({'Content-Type': "application/json"})
        self.url_prefix = f"https://{self.host}:{self.port}/api"

        self.login()

    def login(self) -> None:
        """
        Log in to the Apstra controller.
        """
        url = f"{self.url_prefix}/user/login"
        payload = {
            "username": self.username,
            "password": self.password
        }
        response = self.session.post(url, json=payload)
        # print(f"{response.raw=}")
        self.token = response.json()["token"]
        self.session.headers.update({'AuthToken': self.token})

    def get_device_profile(self, name: str = None) -> dict:
        """
        Get the device profile with the specified name.

        Args:
            name: The name of the device profile.

        Returns:
            The device profile, or None if the device profile does not exist.
        """
        if name is None:
            print("get_device_profile: name is None")
            return None

        url = f"{self.url_prefix}/device-profiles"
        device_profiles = self.session.get(url).json()['items']
        for device_profile in device_profiles:
            # print(f"{device_profile.keys()=}\n {device_profile=}")
            if device_profile['id'] == name:
                return device_profile

        return None

    def get_logical_device(self, id: int) -> dict:
        """
        Get the logical device with the specified ID.

        Args:
            id: The ID of the logical device.

        Returns:
            The logical device, or None if the logical device does not exist.
        """
        url = f"{self.url_prefix}/design/logical-devices/{id}"
        return self.session.get(url).json()

    def get_items(self, url: str) -> dict:
        """
        Get the items from the url.

        Args:
            The url under /api

        Returns:
            The items
        """
        url = f"{self.url_prefix}/{url}"
        return self.session.get(url).json()

    def patch_item(self, url: str, spec: dict) -> dict:
        """
        Patch an items.

        Args:
            The url under /api/
            The patch spec

        Returns:
            The return
        """
        url = f"{self.url_prefix}/{url}"
        print(f"patch_item({url}, {spec})")
        return self.session.patch(url, json=spec).json()



    def print_token(self) -> None:
        """
        Print the current authentication token.
        """
        print(f"{self.token=}")


if __name__ == "__main__":
    apstra = CkApstraSession("10.85.192.50", 443, "admin", "zaq1@WSXcde3$RFV")
    apstra.print_token()
