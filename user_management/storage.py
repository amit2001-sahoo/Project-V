import base64
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from decouple import config
from datetime import datetime, timezone, timedelta


class AzureBlobStorage:
    def __init__(self):
        self.container_name = config("AZURE_STORAGE_CONTAINER")
        self.account_name = config("AZURE_STORAGE_ACCOUNT_NAME")
        self.storage_connection_string = config("AZURE_STORAGE_CONNECTION_STRING")
        self.account_key = config("AZURE_ACCOUNT_KEY")
        self.blob_service_client = BlobServiceClient.from_connection_string(self.storage_connection_string)

    def upload_file(self, file_content, blob_name):
        blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=blob_name)
        blob_client.upload_blob(file_content, overwrite=True)

    def delete_file(self, blob_name):
        blob_client = self.blob_service_client.get_blob_client(container=self.container_name,
                                                               blob=blob_name)
        blob_client.delete_blob()

    def get_file_url(self, blob_name):
        return f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob_name}"

    def generate_blob_sas_token(self, blob_name, permission=BlobSasPermissions(read=True), expiry_minutes=5):
        """
        Generate a SAS token for the specified blob with the given permissions and expiry time.

        :param blob_name: Name of the blob.
        :param permission: Permissions to grant for the SAS token. Default is read-only.
        :param expiry_minutes: Expiry time for the SAS token in minutes. Default is 5 minutes.
        :return: SAS token for the blob.
        """
        # Define the start time and expiry time for the SAS token
        start_time = datetime.now(timezone.utc)
        expiry_time = start_time + timedelta(minutes=expiry_minutes)

        # Generate the SAS token
        sas_token = generate_blob_sas(
            account_name=self.account_name,
            container_name=self.container_name,
            blob_name=blob_name,
            account_key=self.account_key,  # Only required for generating SAS token locally
            permission=permission,
            start=start_time,
            expiry=expiry_time
        )

        return sas_token

    def download_blob_to_base64(self, blob_path):
        """
        Download the blob from the given URL and convert its content to a base64-encoded string.

        :param blob_path: path of the blob.
        :return: Base64-encoded string of the blob's content.
        """

        blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=blob_path)
        # Download the blob
        blob_data = blob_client.download_blob().readall()
        # Convert the blob data to base64
        blob_base64 = base64.b64encode(blob_data).decode('utf-8')
        return blob_base64

    def move_file(self, source_blob_name, destination_blob_name):
        """
        Move a file from one path to another in the Azure Blob Storage.

        :param source_blob_name: The name (path) of the source blob.
        :param destination_blob_name: The name (path) of the destination blob.
        """
        # Get the source and destination blob clients
        source_blob_client = self.blob_service_client.get_blob_client(container=self.container_name,
                                                                      blob=source_blob_name)
        destination_blob_client = self.blob_service_client.get_blob_client(container=self.container_name,
                                                                           blob=destination_blob_name)

        # Copy the source blob to the destination
        copy_source = source_blob_client.url
        destination_blob_client.start_copy_from_url(copy_source)

        # Optionally wait for the copy operation to complete
        properties = destination_blob_client.get_blob_properties()
        copy_status = properties.copy.status

        while copy_status == 'pending':
            properties = destination_blob_client.get_blob_properties()
            copy_status = properties.copy.status

        # If the copy was successful, delete the source blob
        if copy_status == 'success':
            self.delete_file(source_blob_name)
            return True
        else:
            return False

    def __del__(self):
        """
        Destructor to ensure the blob service client connection is closed
        when the object is deleted.
        """
        if self.blob_service_client:
            self.blob_service_client.close()
            print("Blob service client connection closed.")