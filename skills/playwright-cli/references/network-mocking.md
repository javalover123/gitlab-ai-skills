# Network Mocking

Intercept, mock, or block network requests.

## Basic mocking

```bash
# Block requests (404)
pw route "**/*.jpg" --status=404

# Mock with JSON response
pw route "**/api/users" --body='[{"id":1,"name":"Alice"}]' --content-type=application/json

# Mock with custom headers
pw route "**/api/data" --body='{"ok":true}' --header="X-Custom: value"

# Remove headers from requests (e.g. strip auth)
pw route "**/*" --remove-header=authorization

# View active routes
pw route-list

# Remove routes
pw unroute "**/*.jpg"   # remove specific
pw unroute              # remove all
```

## URL pattern syntax

```
**/api/users           exact path match
**/api/*/details       wildcard in path
**/*.{png,jpg,jpeg}    match extensions
**/search?q=*          match query params
```

## Advanced: conditional responses

```bash
pw run-code "async page => {
  await page.route('**/api/login', route => {
    const body = route.request().postDataJSON();
    if (body.username === 'admin') {
      route.fulfill({ body: JSON.stringify({ token: 'mock-token' }) });
    } else {
      route.fulfill({ status: 401, body: JSON.stringify({ error: 'Invalid' }) });
    }
  });
}"
```

## Modify real responses

```bash
pw run-code "async page => {
  await page.route('**/api/user', async route => {
    const response = await route.fetch();
    const json = await response.json();
    json.isPremium = true;
    await route.fulfill({ response, json });
  });
}"
```

## Simulate failures

```bash
pw run-code "async page => {
  await page.route('**/api/endpoint', route => route.abort('internetdisconnected'));
}"
# abort options: connectionrefused, timedout, connectionreset, internetdisconnected
```

## Add delay

```bash
pw run-code "async page => {
  await page.route('**/api/slow', async route => {
    await new Promise(r => setTimeout(r, 3000));
    route.fulfill({ body: JSON.stringify({ data: 'loaded' }) });
  });
}"
```

## Inspect network traffic

```bash
pw network   # list all requests since page load
pw console   # list console messages
pw console warning   # filter by level (log, info, warning, error)
```
