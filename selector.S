/* Experimental nuwa entry stub. For temporary fastboot testing only.
 * Android boot entry x0-x3 are preserved on the Android path.
 * SPMI v7 layout and PM8550 GPIO status are derived from the local
 * mainline spmi-pmic-arb and pinctrl-spmi-gpio drivers and nuwa DT.
 * If the peripheral is missing, denied, failed or times out: Android.
 * A synchronous MMIO abort cannot be caught by this stub.
 */
.text
_KernelHead:
    .space 4
_AndroidEntry:
    .space 28
_FdBase:
    .quad 0
_FdSize:
    .quad 0
_KernelSize:
    .quad 0
    .space 8
_Selector:
    /* PMIC arbiter core 0x0c400000; accept only version 7. */
    movz x5, #0x0c40, lsl #16
    ldr w6, [x5]
    lsr w6, w6, #28
    cmp w6, #7
    b.ne _Android
    ldr w6, [x5, #4]
    and w6, w6, #0x7ff
    cbz w6, _Android
    cmp w6, #1024
    b.hi _Android

    /* v7 bus 0 APID table; PMK8550 SID 0, PON HLOS PPID 0x13. */
    add x7, x5, #2, lsl #12
    movz x8, #0x0c42, lsl #16
    add x8, x8, #0xd, lsl #12  /* owner table: 0x0c42d000 */
    mov w11, #-1                 /* selected APID */
    mov w4, #0
_Scan:
    ldr w9, [x7, x4, lsl #2]
    cbz w9, _Next
    ubfx w10, w9, #8, #12
    cmp w10, #0x13
    b.ne _Next
    cmn w11, #1
    csel w11, w4, w11, eq       /* first match */
    ldr w10, [x8, x4, lsl #2]
    tst w10, #7
    csel w11, w4, w11, eq       /* prefer AP execution environment */
_Next:
    add w4, w4, #1
    cmp w4, w6
    b.lo _Scan
    cmn w11, #1
    b.eq _Android

    /* Observer channel at 0x0c440000 + APID*0x20, EE 0. */
    movz x7, #0x0c44, lsl #16
    add x7, x7, x11, lsl #5
    /* Allow a two-second window after kernel entry. Sample every 20 ms. */
    mrs x13, cntfrq_el0
    cbz x13, _Android
    lsl x14, x13, #1             /* window length in counter ticks */
    mov x17, #50
    udiv x16, x13, x17           /* sample interval: 20 ms */
    cbz x16, _Android
    mrs x15, cntvct_el0          /* window start */
    mov w12, #2                  /* require two pressed readings */
_Read:
    movz w9, #0x0100             /* EXT_READL, offset 0x10, 1 byte */
    movk w9, #0x0800, lsl #16
    str w9, [x7]
    dsb sy
    mov w10, #0xffff
_Wait:
    ldr w9, [x7, #8]
    tbnz w9, #0, _Done
    subs w10, w10, #1
    b.ne _Wait
    b _Android
_Done:
    tst w9, #0xe                /* denied, failed or dropped */
    b.ne _Android
    ldr w9, [x7, #0x18]
    tbz w9, #6, _Released       /* GEN3 RESIN status: bit 6 set = pressed */
    subs w12, w12, #1
    b.eq _UEFI
    b _Pause
_Released:
    mov w12, #2
_Pause:
    mrs x17, cntvct_el0
_PauseLoop:
    mrs x9, cntvct_el0
    sub x10, x9, x15
    cmp x10, x14
    b.hs _Android
    sub x10, x9, x17
    cmp x10, x16
    b.lo _PauseLoop
    b _Read
_UEFI:
    adr x4, _KernelHead
    ldr x5, _KernelSize
    add x4, x4, x5
    ldr x5, _FdBase
    ldr x6, _FdSize
    bl _CopyLoop
    adr x0, _ShellCodeEnd
    adr x1, _ShellCodeEnd
    ldr x5, _FdBase
    br x5
_CopyLoop:
    ldp x2, x3, [x4], #16
    stp x2, x3, [x5], #16
    subs x6, x6, #16
    b.ne _CopyLoop
    ret
_Android:
    b _AndroidEntry
.align 4
_ShellCodeEnd:
