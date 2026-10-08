# C Code Quality Rules

## Memory Safety (CRITICAL)

Memory bugs in C don't just crash your program -- they open the door to exploits. Every allocation, every copy, every free needs your attention.

- Check ALL `malloc` returns:
  ```c
  // BAD: char *buf = malloc(size); strcpy(buf, src);
  // GOOD:
  char *buf = malloc(size);
  if (buf == NULL)
      return -ENOMEM;
  ```
- Use bounded string functions: `strlcpy` not `strcpy`, `snprintf` not `sprintf`, NEVER `gets`
- Nullify pointers after free:
  ```c
  free(ptr);
  ptr = NULL;  /* Prevents use-after-free, makes double-free safe */
  ```
- Use the goto cleanup pattern for resource management:
  ```c
  int
  do_work(void)
  {
      int ret = -1;
      char *buf = NULL;
      FILE *fp = NULL;

      buf = malloc(BUFSIZ);
      if (buf == NULL)
          goto cleanup;

      fp = fopen(path, "r");
      if (fp == NULL)
          goto cleanup;

      /* ... actual work ... */
      ret = 0;

  cleanup:
      free(buf);
      if (fp != NULL)
          fclose(fp);
      return ret;
  }
  ```
- Size calculations: always check for overflow before `malloc(count * size)` -- use `calloc` or `reallocarray` when you can

## Undefined Behavior Prevention

The compiler assumes UB never happens. When it does, anything goes -- and "anything" is never good.

- Initialize all variables at declaration
- Check array bounds before access
- Don't do pointer arithmetic beyond array bounds (even one-past-end is only valid for comparison)
- Signed integer overflow is UB -- use unsigned for wrapping arithmetic, or check before operating
- Don't dereference NULL, ever (sounds obvious, but it's the #1 C bug)
- Avoid casts between incompatible pointer types (strict aliasing violations)

## Error Handling

C doesn't have exceptions, so conventions matter. Pick one and stick with it across the project.

- Consistent return code conventions: 0 = success, negative = error
- Check ALL library function returns (yes, even `close()` and `fclose()`)
- Document error codes in headers
- Use `errno` appropriately -- save it immediately if you need it later, since the next call may overwrite it
- OpenBSD style: prefer `err(3)`/`warn(3)` for error reporting in userspace programs

## Header Organization

- Include guards in ALL headers:
  ```c
  #ifndef MYPROJECT_HEADER_H
  #define MYPROJECT_HEADER_H
  /* ... */
  #endif /* MYPROJECT_HEADER_H */
  ```
- Include headers in source files, not in other headers (reduces coupling)
- Forward declare structs instead of including when you only need a pointer
- Follow the include ordering convention from the project's style guide

## Detection Commands

```bash
# Banned functions (these have no business in new code)
rg '\b(gets|strcpy|strcat|sprintf|vsprintf)\s*\(' --type c

# Unchecked malloc (allocation followed by non-null-check)
rg -U '=\s*malloc\([^)]*\);\s*\n\s*[^i]' --type c

# Missing include guards
find . -name '*.h' -exec sh -c \
  'grep -qL "#ifndef\|#pragma once" "$1" && echo "$1"' _ {} \;

# Static analysis
clang-tidy --checks='-*,cert-*,bugprone-*' file.c
cppcheck --enable=all src/
```

## Compiler Flags (Required)

Don't ship code that wasn't built with warnings cranked up. These flags catch real bugs.

```bash
gcc -Wall -Wextra -Wpedantic -Werror \
    -Wshadow -Wconversion -Wformat=2 \
    -fsanitize=address,undefined \
    -fstack-protector-strong
```

And during development, also consider `-Wcast-qual`, `-Wstrict-prototypes`, and `-Wmissing-prototypes`.

## Testing

- Unity, CMocka, or Check frameworks for unit tests
- Run with ASan + UBSan enabled -- they'll catch things your tests don't explicitly check
- Valgrind for memory leak detection (when ASan isn't available)
- Fuzz with AFL++ or libFuzzer for parsing code and anything that handles external input
