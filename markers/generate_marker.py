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
import struct
import zlib

ROOT_POLYNOM = 0x4C11DB7


def load_pages(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def parse_unit(value: str):
    # Def SI units
    orders = ["u", "m", "k", "M", "G"]
    factor = [1e-6, 1e-3, 1e3, 1e6, 1e9]

    # First, replace unit with nothing
    tmp = value.replace("Hz", "").replace("A", "").replace("V", "")

    # Get the factor
    if tmp[-1] in orders:
        data = tmp[:-1]
        fact = factor[orders.index(tmp[-1])]
    else:
        data = tmp
        fact = 1

    # Cast
    return float(data) * fact


def calculate_crc16(data: bytes) -> int:
    crc = 0x0000
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return crc


def build_peripheral_page(config):
    enabled_mask = 0

    # Build UARTs
    uart_blocks = b""
    for i in range(3):
        uart_key = f"uart{i}"
        if uart_key in config:
            enabled_mask |= 1 << i
            baud = config[uart_key].get("baudrate", 115200) // 100
            ctrl = 0x08  # Default 8N1
            uart_blocks += struct.pack("<HB", baud, ctrl)
        else:
            uart_blocks += struct.pack("<HB", 0, 0)

    # Build SPI
    spi_block = b""
    if "spi" in config:
        enabled_mask |= 1 << 5
        spi_baud = parse_unit(config["spi"].get("baudrate", "1MHz"))
        spi_size = int(config["spi"].get("size", 8))
        spi_block = struct.pack("<HB", spi_baud, spi_size)
    else:
        spi_block = struct.pack("<HB", 0, 0)

    # Build CAN
    can_block = struct.pack("<BBH", 0, 0, 0)

    # Build JTAG
    jtag_block = struct.pack("<HH", 0, 0)

    # Build I2C
    i2c_block = struct.pack("<BBB", 0, 0, 0)

    page_body = struct.pack(
        "<HBB9s3s4s4s3sB",
        enabled_mask,
        0,
        0,
        uart_blocks,
        spi_block,
        can_block,
        jtag_block,
        i2c_block,
        0,
    )
    marker = 0xEBB2
    crc16 = calculate_crc16(struct.pack("<H", marker) + page_body)
    periph_bytes = struct.pack("<HH", marker, crc16) + page_body
    return (marker, periph_bytes)


def build_name_page(config):
    marker = 0xEBB3
    raw_name = config["name"].encode("ascii")[:28]
    padded_name = raw_name.ljust(28, b"\x00")
    crc16 = calculate_crc16(struct.pack("<H", marker) + padded_name)
    name_bytes = struct.pack("<HH28s", marker, crc16, padded_name)
    return (marker, name_bytes)


def build_calibration_page(config):
    marker = 0xEBB4
    cal = config["calibration"]
    cal_body = struct.pack(
        "<ffffffHBB",
        float(parse_unit(cal.get("adc0_offset", "0V"))),
        float(parse_unit(cal.get("adc1_offset", "0V"))),
        float(cal.get("adc_gain", 1.0)),
        float(parse_unit(cal.get("dac0_offset", "0V"))),
        float(parse_unit(cal.get("dac1_offset", "0V"))),
        float(cal.get("dac_gain", 1.0)),
        int(cal.get("year", 2026)),
        int(cal.get("month", 1)),
        int(cal.get("day", 1)),
    )
    crc16 = calculate_crc16(struct.pack("<H", marker) + cal_body)
    cal_bytes = struct.pack("<HH", marker, crc16) + cal_body
    return (marker, cal_bytes)


def build_main_page(config, opt_page_ptrs):
    flags_mask = 0
    flag_map = {
        "isolated": 1 << 0,
        "require_clock": 1 << 1,
        "require_usb": 1 << 2,
        "active_board": 1 << 3,
        "non_standard_form_factor": 1 << 6,
        "ignore_mounting_check": 1 << 7,
    }
    for flag in config.get("flags", []):
        if flag in flag_map:
            flags_mask |= flag_map[flag]

    hw_version_str = config.get("version", "0.0.0")
    major, minor, patch = map(int, hw_version_str.split("."))
    hw_version_encoded = (major << 24) | (minor << 16) | (patch << 8)

    page0_body = struct.pack(
        "<HHIHHHHHHII",
        0xEBB0,
        0x1000,
        hw_version_encoded,
        round(parse_unit(config.get("std_voltage", "0.0V")) * 1000),
        round(parse_unit(config.get("max_current", "0A")) * 1000),
        round(parse_unit(config.get("min_voltage", "0.0V")) * 1000),
        round(parse_unit(config.get("max_voltage", "0.0V")) * 1000),
        flags_mask,
        round(parse_unit(config.get("clock", "0MHz"))),
        opt_page_ptrs[0],
        opt_page_ptrs[1],
    )

    # Add the CRC
    config_crc = zlib.crc32(page0_body)
    return page0_body + struct.pack("<I", config_crc)


def build_page_table(opt_pages):

    # Check if we need to add another page for it
    if len(opt_pages) < 3:
        opt_page_ptrs = [0xFFFFFFFF, 0xFFFFFFFF]
        current_offset = 32

        for i, (p_type, _) in enumerate(opt_pages):
            opt_page_ptrs[i] = current_offset | (p_type << 16)
            current_offset += 32
        return (opt_pages, opt_page_ptrs)

    # Else, we need a new page for it:
    elif len(opt_pages) < 9:
        print("    * INFO * Added a new page table.")

        # Constant to the add-on pages
        marker = 0xEBB1
        pages = [32 | (marker << 16)]

        current_offset = 64
        for i, (p_type, _) in enumerate(opt_pages):
            pages.append(current_offset | (p_type << 16))
            current_offset += 32

        # Build the page
        page_body = struct.pack("<I", pages[2])
        for page in pages[3:]:
            page_body = page_body + struct.pack("<I", page)

        # Adding filler data to hold the page alignement
        missing_pages = 7 - len(pages[3:]) - 1
        for missing_page in range(missing_pages):
            page_body = page_body + struct.pack("<I", 0xFFFFFFFF)

        # Add the CRC value
        crc16 = calculate_crc16(struct.pack("<H", 0xEBB1) + page_body)
        page_bytes = struct.pack("<HH", 0xEBB1, crc16) + page_body

        # Insert ourselves as the first page (thus, we'll be in page 0)
        opt_pages.insert(0, (0xEBB1, page_bytes))

        # Build the array
        opt_page_ptrs = pages[:2]
        return (opt_pages, opt_page_ptrs)
    else:
        print(
            "    * ERROR * Requested too much pages. Could not fit them on the protocol"
        )
        return ([], [])


def build_pages(data: dict):
    optional_pages = []

    has_periph = any(
        k in config for k in ["uart0", "uart1", "uart2", "spi", "can", "jtag", "i2c"]
    )
    if has_periph:
        print("    * INFO * Including peripheral configuration table")
        optional_pages.append(build_peripheral_page(data))

    if "name" in config:
        print("    * INFO * Including page name table")
        optional_pages.append(build_name_page(data))

    if "calibration" in config:
        print("    * INFO * Including calibration table")
        optional_pages.append(build_calibration_page(data))

    # Calculating the pages requirements
    optional_pages, opt_page_ptrs = build_page_table(optional_pages)

    # Build the main page
    page0_bytes = build_main_page(config, opt_page_ptrs)

    # Assemble all pages together
    full_binary = page0_bytes
    for _, p_bytes in optional_pages:
        full_binary += p_bytes

    return full_binary


if __name__ == "__main__":

    # Create the parser
    parser = argparse.ArgumentParser()
    parser.description = "Generate the binary blob in two different format, else a C formatted struct, or a raw binary blob."
    parser.epilog = "Wrote for the EtherBench project. 22/05/2026"
    parser.add_argument("source", help="The config file for the config.")
    parser.add_argument("target", help="The output file.")

    args = parser.parse_args()

    # Load the config
    config = load_pages(args.source)

    # # Build the pages
    data = build_pages(config)

    # Write the raw binary file
    bin_filename = f"{args.target}.bin"
    with open(bin_filename, "wb") as f_bin:
        f_bin.write(data)

    h_filename = f"{args.target}.h"
    hex_lines = []
    for i in range(0, len(data), 12):
        chunk = data[i : i + 12]
        hex_str = ", ".join(f"0x{b:02X}" for b in chunk)
        hex_lines.append(f"    {hex_str},")

    formatted_hex = "\n".join(hex_lines).rstrip(",")

    header_template = f"""/**
 * @file {h_filename}
 * @brief Auto-generated hardware marker configuration for EtherBench daughter-boards.
 * @note Generated automatically from local specification layout. Do not edit.
 */

#ifndef {args.target.upper()}_H
#define {args.target.upper()}_H

#include <stdint.h>

#define {args.target.upper()}_SIZE_BYTES  {len(data)}

/**
 * @brief Static raw binary image of the extension board marker.
 */
static const uint8_t {args.target}_img[{args.target.upper()}_SIZE_BYTES] = {{
{formatted_hex}
}};

#endif /* {args.target.upper()}_H */
"""

    with open(h_filename, "w", encoding="utf-8") as f_h:
        f_h.write(header_template)

    print(f"--> Generated raw binary file : {bin_filename} ({len(data)} bytes)")
    print(f"--> Generated C header file : {h_filename}")
