ENTRY(lt_entry1)
SECTIONS {
  . = 0x10009000;
  .text : { KEEP(*(.text.lt_entry0)) KEEP(*(.text.lt_entry1)) *(.text*) *(.rodata*) }
  .data : { *(.data*) *(.bss*) *(COMMON) }
  _end_slot = .;
  /DISCARD/ : { *(.ARM.*) *(.comment) }
}
ASSERT(_end_slot <= 0x10009600, "FX2 code + data must stay below the 8 KB buffer at 0x1000A000");
