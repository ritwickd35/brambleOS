ENTRY(cw_entry1)
SECTIONS {
  . = 0x33800;
  .text : { KEEP(*(.text.cw_entry0)) KEEP(*(.text.cw_entry1)) *(.text*) *(.rodata*) }
  .data : { *(.data*) *(.bss*) *(COMMON) }
  _end = .;
  /DISCARD/ : { *(.ARM.*) *(.comment) }
}
ASSERT(SIZEOF(.data) == 0, "no RAM data allowed");
