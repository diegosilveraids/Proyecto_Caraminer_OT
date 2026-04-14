import json
import os

def get_credential(target_name: str) -> tuple[str, str]:
    import win32cred
    """
    Retrieves the credentials stored with id: target_name 
    from Windows Credential Manager
    """
    try:
        cred = win32cred.CredRead(target_name, win32cred.CRED_TYPE_GENERIC)
        username = cred['UserName']
        password = cred['CredentialBlob'].decode('utf-16')
        return username, password
    except Exception as e:
        raise RuntimeError(f"No se pudo obtener la credencial '{target_name}': {e}")

# Get the environment and project path from Rocketbot
env = GetVar("ENV")  # dev / test / prod
project_path = GetVar("PROJECT_PATH")

# Define the path of config file to be used
ruta_config = os.path.join(project_path, "config", f"{env}.json")

with open(ruta_config, "r", encoding="utf-8") as archivo:
    configuracion = json.load(archivo) # get the configuration 

# Process Input Files paths
input_files = configuracion.get("input_files", {})
for clave, valor in input_files.items():
    if not valor: # If its empty, use {PROJECT_PATH}/input by default
        nueva_ruta = os.path.join(project_path, "input")
    elif os.path.isabs(valor): # If the path is absolute leave as it is
        nueva_ruta = valor
    else: # If path is relative then: PROJECT_PATH/input/{valor}
        nueva_ruta = os.path.join(project_path, "input", valor)

    nueva_ruta = nueva_ruta.replace("\\", "/") # standardize the output
    SetVar(clave, nueva_ruta)

# Process Output Files paths
output_files = configuracion.get("output_files", {})
for clave, valor in output_files.items():
    if not valor: # If its empty, use {PROJECT_PATH}/input by default
        nueva_ruta = os.path.join(project_path, "output")
    elif os.path.isabs(valor): # If the path is absolute leave as it is
        nueva_ruta = valor
    
    else: # If path is relative then: PROJECT_PATH/input/{valor}
        nueva_ruta = os.path.join(project_path, "output", valor)

    nueva_ruta = nueva_ruta.replace("\\", "/") # standardize the output
    SetVar(clave, nueva_ruta)


# Process the Credentials
credentials = configuracion.get("credentials", {})
for cred_id, cred_var in credentials.items():
    if not cred_var: # If there is no credential destination variable defined
        raise Exception(f"No esta definido a que variable van las credenciales de clave {cred_id}.")
    try:
        user, password = get_credential(str(cred_id)) # Retrieve the credentials
    except Exception as e:
        raise Exception(
            f"No se pudieron obtener las credenciales para '{cred_id}'. "
            f"Detalle: {str(e)}"
        )
    if "key" in user.lower():
        SetVar(f"{cred_var}_key", password)
    else:
        SetVar(f"{cred_var}_user", user)
        SetVar(f"{cred_var}_pass", password)


# Get the rest of the configuration
for clave, valor in configuracion.items():
    if clave not in ["input_files", "output_files", "credentials"]:
        SetVar(clave, valor)
