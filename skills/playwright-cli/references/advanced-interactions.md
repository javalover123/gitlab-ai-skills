# Advanced Interactions

## Waiting for elements / page state

When content loads asynchronously, use `run-code` to wait:

```bash
# Wait for element to appear
pw run-code "async page => {
  await page.waitForSelector('.result', { timeout: 10000 });
}"

# Wait for loading spinner to disappear
pw run-code "async page => {
  await page.waitForSelector('.loading', { state: 'hidden' });
}"

# Wait for network to settle
pw run-code "async page => {
  await page.waitForLoadState('networkidle');
}"

# Wait for condition
pw run-code "async page => {
  await page.waitForFunction(() => window.appReady === true);
}"
```

After waiting, take a fresh snapshot to get updated refs:
```bash
pw snapshot
```

## Iframes

CLI commands only work on the main frame. Use `run-code` for iframes:

```bash
pw run-code "async page => {
  const frame = page.locator('iframe#my-iframe').contentFrame();
  await frame.locator('button').click();
}"

# Get all frame URLs
pw run-code "async page => {
  return page.frames().map(f => f.url());
}"
```

## File uploads

```bash
pw upload ./document.pdf        # upload to active file input
pw upload ./file1.pdf ./file2.pdf  # multiple files
```

For hidden file inputs:
```bash
pw run-code "async page => {
  await page.locator('input[type=file]').setInputFiles('./document.pdf');
}"
```

## File downloads

```bash
pw run-code "async page => {
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.click('a.download-link')
  ]);
  await download.saveAs('./downloaded-file.pdf');
  return download.suggestedFilename();
}"
```

## Dialogs

**Set up handler BEFORE triggering the dialog:**

```bash
pw dialog-accept           # accept next alert/confirm/prompt
pw dialog-accept "text"    # type text into prompt then accept
pw dialog-dismiss          # dismiss next dialog

# Then trigger the action that opens the dialog
pw click e5
```

## Drag and drop

```bash
pw drag e2 e8   # drag from e2 to e8
```

## Keyboard shortcuts

```bash
pw press "Control+A"      # select all
pw press "Control+C"      # copy
pw keydown Shift
pw click e5               # shift+click
pw keyup Shift
```

## Mouse precision

```bash
pw mousemove 150 300   # absolute coordinates
pw mousedown           # left button down
pw mouseup
pw mousedown right     # right click
pw mousewheel 0 300    # scroll down
```

## Permissions and emulation

```bash
# Geolocation
pw run-code "async page => {
  await page.context().grantPermissions(['geolocation']);
  await page.context().setGeolocation({ latitude: 37.7749, longitude: -122.4194 });
}"

# Dark mode
pw run-code "async page => {
  await page.emulateMedia({ colorScheme: 'dark' });
}"

# Viewport
pw resize 1920 1080
```

## Executing arbitrary JavaScript

```bash
pw eval "document.title"
pw eval "el => el.getAttribute('data-id')" e5

# More complex JS via run-code
pw run-code "async page => {
  return await page.evaluate(() => ({
    url: location.href,
    items: [...document.querySelectorAll('.item')].map(el => el.textContent)
  }));
}"
```
