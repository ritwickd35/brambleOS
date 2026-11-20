#!/bin/sh
# build the pedal modules in Docker (arm-none-eabi-gcc 14)
cd "$(dirname "$0")"
docker run --rm -v "$PWD":/w -w /w pmarm sh -c '
F="-mcpu=cortex-m4 -mthumb -mfloat-abi=hard -mfpu=fpv4-sp-d16 -Os -ffreestanding -nostdlib -fno-builtin -ffunction-sections -fdata-sections -fsingle-precision-constant -Wall -Wno-unused-function"
set -e
arm-none-eabi-gcc $F -c pmfx.c ds1.c gate.c mod_ds1.c mod_gate.c
arm-none-eabi-gcc $F -T link-fx1.ld -Wl,--gc-sections -nostartfiles pmfx.o ds1.o mod_ds1.o -o mod_ds1.elf -lgcc
arm-none-eabi-gcc $F -T link-nr.ld -Wl,--gc-sections -nostartfiles pmfx.o gate.o mod_gate.o -o mod_gate.elf -lgcc
for m in mod_ds1 mod_gate; do arm-none-eabi-objcopy -O binary -j .text $m.elf $m.bin; arm-none-eabi-nm $m.elf | grep -E " lt_entry[01]$" > $m.sym; done
ls -l mod_ds1.bin mod_gate.bin | awk "{print \$9, \$5}"'
