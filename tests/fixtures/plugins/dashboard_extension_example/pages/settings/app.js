const api = window.AstrBotPluginPage;
const context = await api.ready();

const heading = document.createElement('h1');
heading.textContent = `${context.plugin_name}: Settings`;

const button = document.createElement('button');
button.type = 'button';
button.textContent = 'Read settings';

const output = document.createElement('output');
output.setAttribute('aria-live', 'polite');

button.addEventListener('click', async () => {
  try {
    const result = await api.invoke('settings.read', {});
    output.textContent = result.message;
  } catch (error) {
    output.textContent = error?.message ?? 'Request failed';
  }
});

document.body.append(heading, button, output);
