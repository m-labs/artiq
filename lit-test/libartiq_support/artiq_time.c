#include <stdint.h>
#include <stdio.h>

int64_t now = 0;

int watchdog_set(int ms)
{
  printf("watchdog_set %d\n", ms);
  return ms;
}

void watchdog_clear(int id)
{
  printf("watchdog_clear %d\n", id);
}
