# =========================================================================
# Generate_marker.py
#
# Generate binary blobs for any add-ons boards
# 22/05/2025
# l.heywang
#
# =========================================================================

import argparse
import yaml
import zlib

ROOT_POLYNOM = 0x4C11DB7


def validate_pages(pageId: int, pages) -> bool:
    return True


if __name__ == "__main__":

    # Create the parser
    parser = argparse.ArgumentParser()
    parser.description = "Generate the binary blob in two different format, else a C formatted struct, or a raw binary blob."
    parser.epilog = "Wrote for the EtherBench project. 22/05/2026"

    parser.add_argument(
        "--binary",
        action="store_true",
        default=False,
        help="Set the output to be a binary blob.",
    )

    parser.add_argument("source", required=True, help="The config file for the config.")
