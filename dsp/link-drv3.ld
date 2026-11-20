ENTRY(drv_entry1)
SECTIONS {
  . = 0x10002800;
  .text : { KEEP(*(.text.drv_entry0)) KEEP(*(.text.drv_entry1)) *(.text*) *(.rodata*) }
  .data : { *(.data*) *(.bss*) *(COMMON) }
  _end_slot = .;
  /DISCARD/ : { *(.ARM.*) *(.comment) }
}

ASSERT(_end_slot <= 0x10003800, "DRV slot RAM overflow");
