ENTRY(rv0_e1)
MEMORY { A (rx) : ORIGIN = 0x29500, LENGTH = 3264
         B (rx) : ORIGIN = 0x2E5C0, LENGTH = 3264 }
SECTIONS {
  .ta : { /tmp/reverb.o(.text* .rodata*) } > A
  .tb : { KEEP(*(.text.rv*_e0)) KEEP(*(.text.rv*_e1)) *(.text*) *(.rodata*) } > B
  .data : { *(.data*) *(.bss*) *(COMMON) } > B
  /DISCARD/ : { *(.ARM.*) *(.comment) }
}
ASSERT(SIZEOF(.data) == 0, "no RAM data allowed (in-place code)");
