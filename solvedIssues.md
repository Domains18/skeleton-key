# issues encountered and steps to overcome them
### [mysql] ERROR 1698 (28000): Access denied for user 'root'@'localhost'
  - first login using sudo aas in
  -  `sudo mysql -u root`
  - `CREATE USER 'alpha'@'localhost' IDENTIFIED BY 'alphauser@domains18;'`
### [mysql] your password does not satisfy the current policy
  - `UNINSTALL COMPONENT 'file://component_validate_password';`
