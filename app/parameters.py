# Azure SQL Database parameters
######## CHANGE THE FOLLOWING ###########
server='myservername.database.windows.net'
database='db_name'
dbo_table='dbo.table_name'
username='username@myservername'
password='mypassword'
driver= '{ODBC Driver 17 for SQL Server}'
#########################################

# Used to decode category predictions
label_mapping = {
    "Cash" : "1",
    "Vacances" : "2",
    "Alimentaire" : "3",
    "Restaurants" : "4",
    "Boutiques" : "5",
    "Transports" : "6",
    "Revenus" : "7",
    "Jeux" : "8",
    "Prelevements" : "9",
    "Maison" : "10",
    "Sante" : "11",
    "Tabac" : "12",
    "Loisir" : "13",
    "Essence" : "14",
    "Divers" : "15",
}