ENTRY(st_entry1)
SECTIONS {
  . = 0x10003800;
  .text : { KEEP(*(.text.st_entry0)) KEEP(*(.text.st_entry1)) *(.text*) KEEP(*(.rodata.stab)) *(.rodata*) }
  _end_stub = .;
  /DISCARD/ : { *(.ARM.*) *(.comment) *(.data*) *(.bss*) }
}
ASSERT(_end_stub <= 0x10003C00, "clone stub too big");
