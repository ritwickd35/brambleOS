ENTRY(lt_entry1)
SECTIONS {
  . = 0x10002800;
  .text : { KEEP(*(.text.lt_entry0)) KEEP(*(.text.lt_entry1)) *(.text*) *(.rodata*) }
  .data : { *(.data*) *(.bss*) *(COMMON) }
  _end_slot = .;
  /DISCARD/ : { *(.ARM.*) *(.comment) }
}
ASSERT(_end_slot <= 0x10002900, "DRV stub overflow");
