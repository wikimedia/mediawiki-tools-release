#!/usr/bin/python3

import argparse
import functools
import json
import random
import sys
import re
import subprocess

BASE_RSYNC_ARGS = ["-a", "--stats", "--delete", "--delete-excluded"]


class App():
    def __init__(self, args):
        self.default_base_image = args.default_base_image
        self.rsync_source = args.rsync_source
        self.rsync_dest = args.rsync_dest
        self.layer = args.layer
        self.rsync_transfer_pct_max = args.rsync_transfer_pct_max
        self.max_layers = args.max_layers

        self.rsync_filters = []
        for path in args.include:
            self.rsync_filters.append("--include")
            self.rsync_filters.append(path)
        for path in args.exclude:
            self.rsync_filters.append("--exclude")
            self.rsync_filters.append(path)

    def select_base_image(self) -> str:
        image = self.layer if self.layer else self.default_base_image

        if not self.image_is_suitable_as_base(image):
            print("Falling back to {}".format(self.default_base_image))
            return self.default_base_image

        return image

    def image_is_suitable_as_base(self, image: str) -> bool:
        if image == self.default_base_image:
            # The default base image is always suitable.
            return True

        if not image_exists_locally(image):
            print("{} does not exist locally".format(image))
            # Nonexistent images are not suitable.
            return False

        if not is_descendent_of(image, self.default_base_image):
            print("{} is not a descendent of {}".format(
                image, self.default_base_image))
            return False

        num_layers = count_image_layers(image)

        if num_layers >= self.max_layers:
            print(
                "Image {} is not suitable as a base image because it has {} layers (max is {}).".format(
                    image,
                    num_layers,
                    self.max_layers))
            return False

        if self.rsync_transfer_pct_max is not None:
            rsync_transferpct = self.get_rsync_transfer_pct(image)
            if rsync_transferpct > self.rsync_transfer_pct_max:
                # The candidate base image doesn't provide sufficient data
                # transfer savings.
                print(
                    "Image {} is not suitable due to rsync transfer pct {} (threshold is {})".format(
                        image, rsync_transferpct, self.rsync_transfer_pct_max))
                return False

        # Looks ok
        return True

    def run_rsync(self,
                  image: str,
                  rsync_args=[],
                  capture_output=False,
                  quiet=False) -> str:
        """
        Start a container from 'image' and run rsync in it to copy from the source directory
        on the host to the destination directory in the container.

        If capture_output is True, the return value is a string containing the output
        of the rsync execution.

        If capture_output is False, the return value is the name of the (stopped) container
        where rsync executed.
        """

        container_id = generate_container_id()

        cmd = ["docker",
               "run",
               "--name={}".format(container_id),
               "--rm={}".format("true" if capture_output else "false"),
               "-v",
               "{}:/workdir:ro".format(self.rsync_source),
               "--entrypoint",
               "/usr/bin/rsync",
               image] + BASE_RSYNC_ARGS + rsync_args + self.rsync_filters + ["/workdir/",
                                                                             self.rsync_dest]
        if not quiet:
            print(" ".join(cmd))

        if capture_output:
            return subprocess.check_output(cmd, universal_newlines=True)

        try:
            subprocess.run(cmd, check=True)
        # Using BaseException here so that we can react to KeyboardInterrupt
        # properly.
        except BaseException as e:
            print("Caught exception {}.\nTrying to stop container {}".format(
                e, container_id))
            remove_container(container_id)
            raise

        return container_id

    @functools.lru_cache(maxsize=None)
    def estimate_rsync(self, image: str) -> dict:
        print("Estimating rsync to {}".format(image))
        output = self.run_rsync(image,
                                rsync_args=["-n"],
                                capture_output=True,
                                quiet=True)

        return parse_rsync_stats(output)

    def get_rsync_transfer_pct(self, image: str) -> float:
        stats = self.estimate_rsync(image)

        return (stats["total_transferred_file_size"] /
                stats["total_file_size"]) * 100


def scos(cmd) -> str:
    """Subprocess Checked, Output Stripped"""
    return subprocess.check_output(cmd, universal_newlines=True).strip()


def generate_container_id() -> str:
    return "rsync-{}".format(random.randint(0, sys.maxsize))

# Copied from scap code


def parse_rsync_stats(string: str) -> dict:
    """
    Scans the string looking for text like the following and
    returns a dictionary with the extracted integer fields.

    Note that if no such matching text is found an empty dictionary
    will be returned.

    Number of files: 184,935 (reg: 171,187, dir: 13,596, link: 152)
    Number of created files: 0
    Number of deleted files: 0
    Number of regular files transferred: 1
    Total file size: 8,756,954,367 bytes
    Total transferred file size: 815,772 bytes
    Literal data: 0 bytes
    Matched data: 815,772 bytes
    File list size: 4,744,396
    File list generation time: 0.517 seconds
    File list transfer time: 0.000 seconds
    Total bytes sent: 5,603
    Total bytes received: 4,744,454
    """

    # Keys are header names expected from rsync --stats output.
    # Values are the names of the keys in 'res' that will be used.
    integer_fields = {
        "Number of files": "files",
        "Number of created files": "files_created",
        "Number of deleted files": "files_deleted",
        "Number of regular files transferred": "regular_files_transferred",
        "Total file size": "total_file_size",
        "Total transferred file size": "total_transferred_file_size",
        "Literal data": "literal_data",
        "Matched data": "matched_data",
        "File list size": "file_list_size",
        "Total bytes sent": "total_bytes_sent",
        "Total bytes received": "total_bytes_received",
    }

    res = {}

    for header, key in integer_fields.items():
        m = re.search(header + r": ([\d,]+)", string, re.MULTILINE)
        if m:
            res[key] = int(m.group(1).replace(",", ""))

    return res


def remove_container(id):
    subprocess.run(["docker", "rm", "-f", id], stdout=subprocess.DEVNULL)


def count_image_layers(image: str) -> int:
    return int(scos(["docker", "inspect", image,
                     "--format", "{{len .RootFS.Layers}}"]))


def get_image_entrypoint(image: str) -> str:
    return json.dumps(json.loads(scos(["docker", "image", "inspect", image]))[
                      0]["Config"]["Entrypoint"])


def image_exists_locally(image: str) -> bool:
    output = scos(["docker", "image", "ls", "-q", image])
    return output != ""


def get_image_id(image: str) -> str:
    return scos(["docker", "inspect", "-f", "{{.Id}}", image])


def get_parent(image: str) -> str:
    """
    Returns the id of the parent of 'image'.  If 'image' does not have a
    parent the result will be a blank string.
    """
    return scos(["docker", "inspect", "-f", "{{.Parent}}", image])


def is_descendent_of(image1, image2):
    image2_id = get_image_id(image2)

    image = image1
    while True:
        parent = get_parent(image)

        if not parent:
            return False

        if parent == image2_id:
            return True

        image = parent

################################


def main():
    parser = argparse.ArgumentParser(
        description='Build a container image',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        'default_base_image',
        help='The base image to use if the one specified by --layer is not suitable')
    parser.add_argument('rsync_source',
                        help='The host directory to use as the rsync source')
    parser.add_argument(
        'rsync_dest',
        help='The container directory to use as the rsync destination')
    parser.add_argument('output_image',
                        help='The name of the output image to create')
    parser.add_argument(
        '--layer',
        help='The image to try to layer on top of.  This image must be one generated by this script')
    parser.add_argument(
        '--rsync-transfer-pct-max',
        help='The maximum rsync transfer percentage to accept when determining if the image specified by --layer is suitable',
        type=float,
        default=25)
    # Max layer count of 125 for overlayfs measured on Linux 4.19.0-14-amd64
    parser.add_argument(
        '--max-layers',
        help='The maximum number of layers that LAYER is allowed to have. If exceeded, the default base image will be used',
        type=int,
        default=125)
    parser.add_argument('--exclude',
                        metavar='PATTERN',
                        action='append',
                        help="Exclude files matching PATTERN")
    parser.add_argument('--include',
                        metavar='PATTERN',
                        action='append',
                        help="don't exclude files matching PATTERN")
    args = parser.parse_args()

    app = App(args)

    base_image = app.select_base_image()
    print("Using {} as the base image".format(base_image))

    # Save the original entrypoint of the base image since we override
    # it in the 'docker run' in run_build_container() and 'docker commit' saves that as
    # the entrypoint (if we don't do anything about it, but we do).
    original_entrypoint = get_image_entrypoint(base_image)

    stats = app.estimate_rsync(base_image)
    rsync_args = []
    if stats["regular_files_transferred"] + stats["files_deleted"] <= 100:
        rsync_args.append("-v")

    print("\n** rsync {} to container:{} **".format(app.rsync_source, app.rsync_dest))

    builder_id = app.run_rsync(base_image, rsync_args)
    try:
        print("\nCommit {}".format(args.output_image))

        subprocess.run(["docker", "commit",
                        "-c", "ENTRYPOINT {}".format(original_entrypoint),
                        builder_id, args.output_image],
                       check=True)

        print("{} has {} layers".format(args.output_image,
                                        count_image_layers(args.output_image)))
    finally:
        remove_container(builder_id)

    print("Image build finished")


if __name__ == "__main__":
    main()
