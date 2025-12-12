#!/bin/bash
# Wrapper to run Cooja in no-GUI mode with a given simulation (.csc) file.
# Copy this file into contiki-ng/tools/cooja/ and make it executable.
#
# Usage from tools/cooja:
#   ./cooja_nogui.sh ../../examples/dataset-rpl/cooja_dataset.csc

# Gradle-based Cooja (Contiki-NG 4.x)
./gradlew run --args="--no-gui $1"

# If your Cooja uses ant instead, comment the line above and uncomment:
# ant run_nogui -Dargs=$1
