SECTIONS { . = 0x178000; .text : { KEEP(*(.text.hook)) *(.text*) } .rodata : { *(.rodata*) } /DISCARD/ : { *(.data*) *(.bss*) *(.comment) *(.ARM.*) } }
