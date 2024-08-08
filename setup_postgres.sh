figlet "POSTGRES"
echo "setting up postgres as the primary database"

# -- install specific postgres version --
deb http://apt.postgresql.org/pub/repos/apt/ trusty-pgdg main
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt update -y
sudo -u postgres psql

# -- seting up peer connections for seamless logins --
clear
echo "change paramaters on the permission section from peer to md5 for better db access"
echo "local         all               <your_role>     <address>      md5"
sleep 0.5
sudo vim /etc/postgresql/14/main/pg_hba.conf

sudo systemctl restart postgresql
exec "$SHELL"