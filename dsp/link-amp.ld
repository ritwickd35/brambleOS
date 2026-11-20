ENTRY(amp_entry1)
SECTIONS {
  . = 0x10003800;
  .text : { KEEP(*(.text.amp_entry0)) KEEP(*(.text.amp_entry1)) *(.text*) *(.rodata*) }
  .data : { *(.data*) *(.bss*) *(COMMON) }
  _end_slot = .;
  /DISCARD/ : { *(.ARM.*) *(.comment) }
}
ASSERT(_end_slot <= 0x10006400, "AMP slot RAM overflow");
