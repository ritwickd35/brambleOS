ENTRY(lt_entry1)
SECTIONS {
  . = 0x10001000;
  .text : { KEEP(*(.text.lt_entry0)) KEEP(*(.text.lt_entry1)) *(.text*) *(.rodata*) }
  .data : { *(.data*) *(.bss*) *(COMMON) }
  _end_slot = .;
  /DISCARD/ : { *(.ARM.*) *(.comment) }
}
ASSERT(_end_slot <= 0x10002800, "FX1 slot RAM (6 KB) overflow");
