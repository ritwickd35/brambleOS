ENTRY(core_e1)
SECTIONS {
  . = 0x10003C00;
  .text : { KEEP(*(.text.core_e0)) KEEP(*(.text.core_e1)) *(.text*) *(.rodata*) }
  .data : { *(.data*) *(.bss*) *(COMMON) }
  _end_slot = .;
  /DISCARD/ : { *(.ARM.*) *(.comment) }
}
ASSERT(_end_slot <= 0x10006000, "clone amp core overflow");
