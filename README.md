# Setting up newly installed PostgreSQL on Linux

** To change before running the script **

> add your github username
> add the mail attached to your github
> feel free to change the code, you can also send a PR

## Features to add;

    - [x] install zsh + oh-my-zsh
    - [x] Make updates & uprades
    - [x] Python setup with pyenv
    - [x] setup node dev env (bun, pnpm, nvm and an lts node version)
    - [x] make sure flatpak is installed
    - [x] install brave with flatpak
    - [x] gnome shell extentions + gnome shell ext manager setup
    - [x] database manager (dbeaver)
    - [x] install golang (the newest LTS version )
    - [x] donwload postman (flatpak)
    - [x] Obsidian download (flatpak)
    - [x] search light( redirect to browser to download Search light a gnome plugin )
    - [x] Nvim from build (app image) +  nvchad
    - [x] snapd pkm
    - [x] openssl server

Install PostgreSQL (shell only)

```bash
sudo apt install postgresql
```

Accessing the root role set up by default on PostgreSQL

```bash
sudo -u postgres psql
```

This will access PostgreSQL role that will help up setup our role and database

### Creating our user | database Role

```sql
CREATE USER <rone_name> WITH SUPERUSER PASSWORD <role_password>;
```

This will create a super user role with your specified password.

I prefer creating a **super user role** on my newly installed **PostgreSQL**

### Creating a database and setting the previously created Role

```sql
CREATE DATABASE <db_name> OWNER <role_of_choice>;
```

This will create a database and set the role as the owner. This will allow you to login directly to the database.

### Setting up peer connection auth

```bash
sudo vi /etc/postgresql/<version>/main/pg_hba.conf
```

Now go to connections and add auth method to your role alternatively you can reset all roles auth method.

```bash
# TYPE          DATABASE          USER            ADDRESS        MTEHOD
	local         all               <your_role>     <address>      md5
```

This configuration will allow you to access the database with the password either using the **psql shell** or from an app.

### Saving and loading the changes

```bash
sudo systemctl restart postgresql
```

Now you can access the database with your role name and password

```bash
# eg
psql -d <created_database> -U <created_role>
```