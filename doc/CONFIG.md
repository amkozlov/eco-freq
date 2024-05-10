# EcoFreq config file reference 

## Server

The `[server]` section defines who can use the `ecoctl` command to change EcoFreq settings on-the-fly. It works by changing the ownership of and permissions on the IPC socket file (`/var/run/ecofreq.sock`). By default, this file is owned by `root:ecofreq` with group read/write permissions (`0660`). 

Allow access for members of the `staff` user group:
```
[server]
filegroup=staff
filemode=0o660
```

Allow access for any user (not recommended):
```
[server]
filemode=0o666
```

