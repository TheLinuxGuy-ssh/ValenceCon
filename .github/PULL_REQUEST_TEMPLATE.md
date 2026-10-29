## Summary

Describe the change and the user-visible behavior it affects.

## Validation

- [ ] `python3 -m unittest discover -s tests -v`
- [ ] `python3 -m compileall -q default.py service.py resources tests tools`
- [ ] Built the Kodi add-on archive when packaging changes are involved

## Checklist

- [ ] No API keys, credentials, or private server details are included
- [ ] Documentation and translations are updated where needed
- [ ] The change is compatible with the supported Kodi versions
