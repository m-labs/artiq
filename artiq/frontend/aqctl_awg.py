#!/usr/bin/env python3
"""Controller for Spectrum Instrumentation AWG devices."""

import argparse
import logging
import sys
import time
from pathlib import Path

from sipyco.common_args import (
    simple_network_args,
    bind_address_from_args,
    verbosity_args,
    init_logger_from_args,
)
from sipyco.pc_rpc import simple_server_loop

from artiq.devices.awg.driver import AWGDriver

logger = logging.getLogger(__name__)


def setup_logging(log_file_dir: Path):
    """Setup centralized logging for all modules"""
    log_file_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_file_dir / "oqd-spectrum-ndsp.log"
    
    # Get root logger
    root_logger = logging.getLogger()
    
    # Create file handler
    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    
    # Add file handler to root logger
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.INFO)
    
    # Suppress DEBUG messages from sipyco RPC and asyncio
    logging.getLogger("sipyco.pc_rpc").setLevel(logging.INFO)
    logging.getLogger("asyncio").setLevel(logging.INFO)
    
    return logging.getLogger(__name__), log_file


def get_argparser():
    """Get argument parser for the controller."""
    parser = argparse.ArgumentParser(description="Spectrum Instrumentation AWG controller")
    simple_network_args(parser, 3274)
    verbosity_args(parser)
    parser.add_argument(
        "-d",
        "--device",
        default="/dev/spcm0",
        help="Path to SPCM device (default: /dev/spcm0)",
    )
    parser.add_argument(
        "-r",
        "--reset",
        default=False,
        action="store_true",
        help="Reset device before starting (default: %(default)s)",
    )
    parser.add_argument(
        "--log",
        type=Path,
        default=Path.home() / ".oqd-spectrum-ndsp",
        help="Path to the location for the log file.",
    )
    return parser


def main():
    """Main entry point for the controller."""
    args = get_argparser().parse_args()
    
    # Initialize logging
    logger, log_file_path = setup_logging(args.log.resolve())
    print(f"Logs will be saved to: \033[1;32m{log_file_path}\033[0m")
    
    # Log which file is being used (for debugging version issues)
    import os
    script_path = os.path.abspath(__file__)
    logger.info(f"Running from: {script_path}")
    
    # Initialize console logging (adds console handlers, preserves file handler)
    init_logger_from_args(args)
    
    # Log startup message immediately to verify logging works
    logger.info("=" * 80)
    logger.info("AWG Controller Starting")
    logger.info(f"Device: {args.device}")
    logger.info(f"Port: {args.port}")
    logger.info(f"Log file: {log_file_path}")
    logger.info("=" * 80)
    sys.stdout.flush()

    driver = None
    try:
        logger.info(f"Starting AWG controller on device {args.device}")
        sys.stdout.flush()  # Ensure output is visible
        sys.stderr.flush()  # Logging often goes to stderr
        
        try:
            driver = AWGDriver(device_path=args.device)
            logger.info("AWG driver initialized successfully")
            sys.stdout.flush()
        except Exception as e:
            logger.error(f"Failed to initialize AWG driver: {e}")
            logger.exception("Driver initialization error details")
            sys.stdout.flush()
            raise
        
        if args.reset:
            logger.info("Resetting device")
            sys.stdout.flush()
            driver.reset()
            time.sleep(0.1)

        bind_address = bind_address_from_args(args)
        logger.info(f"Starting RPC server on {bind_address}:{args.port}")
        sys.stdout.flush()
        
        simple_server_loop(
            {"awg": driver},
            bind_address,
            args.port,
            description="device=" + str(args.device),
        )
    except KeyboardInterrupt:
        logger.info("Controller interrupted by user")
        sys.stdout.flush()
    except Exception as e:
        logger.exception(f"Controller error: {e}")
        sys.stdout.flush()
        sys.exit(1)
    finally:
        if driver is not None:
            driver.close()


if __name__ == "__main__":
    main()