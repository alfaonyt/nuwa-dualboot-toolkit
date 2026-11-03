#include <sys/mman.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <unistd.h>

static void *press_later(void *arg) {
    usleep(100000);
    *(volatile uint32_t *)arg = 0x40;
    return NULL;
}

static void *map(uintptr_t addr, size_t length) {
    void *p = mmap((void *)addr, length, PROT_READ|PROT_WRITE|PROT_EXEC,
                   MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED, -1, 0);
    if (p == MAP_FAILED) { perror("mmap"); exit(100); }
    return p;
}
int main(int argc, char **argv) {
    if (argc != 3) return 101;
    int mode = atoi(argv[2]);
    uint8_t *core = map(0x0c400000, 0x3000);
    uint8_t *owner = map(0x0c42d000, 0x4000);
    uint8_t *obs = map(0x0c440000, 0x80000);
    uint8_t *image = map(0x20000000, 0x2000);
    map(0x30000000, 0x1000);
    FILE *f = fopen(argv[1], "rb");
    if (!f || fread(image, 1, 0x190, f) != 0x190) return 102;
    fclose(f);
    *(uint32_t *)(image + 0) = 0x14000010; /* branch to selector */
    *(uint32_t *)(image + 4) = 0xd65f03c0; /* Android branch returns */
    *(uint64_t *)(image + 0x20) = 0x30000000;
    *(uint64_t *)(image + 0x28) = 16;
    *(uint64_t *)(image + 0x30) = 0x400;
    *(uint32_t *)(image + 0x400) = 0xd2800540; /* mov x0, #42 */
    *(uint32_t *)(image + 0x404) = 0xd2800ba8; /* mov x8, #93 */
    *(uint32_t *)(image + 0x408) = 0xd4000001; /* svc #0 */
    *(uint32_t *)core = mode == 4 ? 0x60000000 : 0x70000001;
    *(uint32_t *)(core + 4) = 8;
    if (mode != 3) *(uint32_t *)(core + 0x2000 + 4 * 5) = 0x13 << 8;
    *(uint32_t *)(owner + 4 * 5) = 0;
    *(uint32_t *)(obs + 0x20 * 5 + 8) = mode == 2 ? 3 : mode == 5 ? 0 : 1;
    *(uint32_t *)(obs + 0x20 * 5 + 0x18) = mode == 1 ? 0x40 : 0;
    if (mode == 6) {
        pthread_t thread;
        if (pthread_create(&thread, NULL, press_later, obs + 0x20 * 5 + 0x18)) return 103;
    }
    __builtin___clear_cache((char *)image, (char *)image + 0x2000);
    ((void (*)(void))image)();
    puts("Android branch returned");
    return 0;
}
