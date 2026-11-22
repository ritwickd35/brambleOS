SECTIONS { . = 0xFAB00; .text : { KEEP(*(.text.hook)) *(.text*) } .rodata : { *(.rodata*) } /DISCARD/ : { *(.data*) *(.bss*) *(.comment) *(.ARM.*) *(.sdata*) *(.sbss*) } }
