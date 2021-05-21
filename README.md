# Ansible module
Module for [slapt-get](https://software.jaos.org/), the unofficial Slackware's repository manager

## Usage
```yaml
# Upgrade all installed packages
- slapt_get:
    upgrade: yes
    update_cache: yes
    clean_cache: yes
```
  
```yaml
# Install packages
-  slapt_get:
    name: [ iptables, ipset ]
    clean: yes
```
  
```yaml
# Install set of packages
- slapt_get:
    install_set: kde
    clean: yes
```
