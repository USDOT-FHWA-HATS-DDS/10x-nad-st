import os
from geopandas import GeoDataFrame, read_file
import pyogrio
from typing import Optional, Dict, Iterator
from zipfile import ZipFile


class DataHandler(object):
    def __init__(
        self, column_map: Dict[str, str], mapped_data_dir: Optional[str] = None
    ) -> None:
        self.column_map = column_map
        self.mapped_data_dir = mapped_data_dir
        self.mapped_data_path = (
            os.path.join(
                self.mapped_data_dir,
                self.mapped_data_dir.split("/")[-1] + ".shp",
            )
            if self.mapped_data_dir
            else None
        )
        self.zip_file_path = (
            os.path.join(
                self.mapped_data_dir,
                self.mapped_data_dir.split("/")[-1] + ".zip",
            )
            if self.mapped_data_dir
            else None
        )
        self.gdb_path = (
            os.path.join(
                self.mapped_data_dir,
                self.mapped_data_dir.split("/")[-1] + ".gdb",
            )
            if self.mapped_data_dir
            else None
        )
        self.gdb_zip_file_path = (
            os.path.join(
                self.mapped_data_dir,
                self.mapped_data_dir.split("/")[-1] + "_gdb.zip",
            )
            if self.mapped_data_dir
            else None
        )
        self.valid_renames = {}
        self.__validate_column_map()

    def __validate_column_map(self):
        column_map_reverse = {}

        for key, value in self.column_map.items():
            if value:
                value_lcase = value.lower()
                if value_lcase in column_map_reverse:
                    column_map_reverse[value_lcase].append(key)
                else:
                    column_map_reverse[value_lcase] = [key]
        duplicates = {k: v for k, v in column_map_reverse.items() if len(v) > 1}
        if duplicates:
            duplicate_nad_fields = ", ".join(
                [" & ".join(nad_fields) for nad_fields in list(duplicates.values())]
            )
            raise Exception(
                f"Duplicate inputs found for destination fields: {duplicate_nad_fields}"
            )

    def __rename_columns(self, gdf: GeoDataFrame) -> GeoDataFrame:
        column_map = self.column_map
        column_map["geometry"] = "geometry"
        original_names = {col.lower(): col for col in gdf.columns}
        for nad_column, raw_field in column_map.items():
            orig_matched_name = original_names.get(nad_column.lower())
            if orig_matched_name:
                self.valid_renames[orig_matched_name] = nad_column
                continue
            if raw_field:
                orig_matched_name = original_names.get(raw_field.lower())
                if orig_matched_name:
                    self.valid_renames[orig_matched_name] = nad_column
        gdf = gdf.rename(columns=self.valid_renames)
        return gdf[[col for col in self.valid_renames.values()]]

    def read_file_in_batches(
        self, path: str, table_name: Optional[str] = None, batch_size: int = 100000
    ) -> Iterator[GeoDataFrame]:
        # Get layer name if not provided
        if not table_name:
            layers = pyogrio.list_layers(path)
            if len(layers) == 0:
                return
            table_name = layers[0][0]

        if self.mapped_data_dir:
            os.makedirs(self.mapped_data_dir, exist_ok=True)
            # Remove existing files if any to start fresh
            if os.path.exists(self.mapped_data_path):
                os.remove(self.mapped_data_path)
            if os.path.exists(self.gdb_path):
                import shutil
                shutil.rmtree(self.gdb_path, ignore_errors=True)

        skip_features = 0
        is_first_batch = True

        while True:
            batch_gdf = pyogrio.read_dataframe(
                path,
                layer=table_name,
                skip_features=skip_features,
                max_features=batch_size
            )

            if batch_gdf.shape[0] == 0:
                break

            batch_gdf = self.__rename_columns(batch_gdf)

            if self.mapped_data_dir:
                mode = "w" if is_first_batch else "a"
                os.environ["SHAPE_RESTORE_SHX"] = "YES"
                batch_gdf.to_file(
                    filename=self.mapped_data_path,
                    index=False,
                    mode=mode,
                    engine="pyogrio",
                )
                # Also write to GDB
                batch_gdf.to_file(
                    filename=self.gdb_path,
                    driver="OpenFileGDB",
                    index=False,
                    mode=mode,
                    engine="pyogrio",
                )

            yield batch_gdf

            if batch_gdf.shape[0] < batch_size:
                break

            skip_features += batch_size
            is_first_batch = False
    def finalize(self):
        if self.mapped_data_dir:
            self.__zip_shp()
            self.__zip_gdb()
            return self.zip_file_path, self.gdb_zip_file_path
        return None, None

    def __zip_shp(self):
        zip_filename = os.path.basename(self.zip_file_path)
        # For SHP, we zip all files except the zips and the GDB directory
        gdb_dirname = os.path.basename(self.gdb_path)
        gdb_zip_filename = os.path.basename(self.gdb_zip_file_path)

        with ZipFile(self.zip_file_path, "w") as zipf:
            for root, dirs, files in os.walk(self.mapped_data_dir):
                # Skip the GDB directory itself when zipping SHP
                if gdb_dirname in dirs:
                    dirs.remove(gdb_dirname)

                for file in files:
                    if file == zip_filename or file == gdb_zip_filename:
                        continue
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, self.mapped_data_dir)
                    zipf.write(file_path, arcname=relative_path)

    def __zip_gdb(self):
        with ZipFile(self.gdb_zip_file_path, "w") as zipf:
            # We only want to zip the contents of the GDB directory
            for root, dirs, files in os.walk(self.gdb_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    # We want the arcname to start with the .gdb directory name
                    relative_path = os.path.relpath(file_path, os.path.dirname(self.gdb_path))
                    zipf.write(file_path, arcname=relative_path)
