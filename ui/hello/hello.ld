SECTIONS { . = 0x178000; .text : { *(.text*) *(.rodata*) } /DISCARD/ : { *(.data*) *(.bss*) *(.comment) } }
