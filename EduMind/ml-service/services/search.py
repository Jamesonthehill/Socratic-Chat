from pathlib import Path
from typing import Any, Optional, Tuple, Union, AsyncGenerator

from graphrag.config.load_config import load_config
from graphrag.utils.api import create_storage_from_config
from graphrag.utils.storage import load_table_from_storage
from graphrag.api.query import (
    basic_search,
    basic_search_streaming,
    local_search,
    local_search_streaming,
    global_search,
    global_search_streaming,
    drift_search,
    drift_search_streaming,
)

class QueryClient:
    def __init__(
        self,
        project_root: str = ".",
        config_file: Optional[str] = None,
        data_dir: Optional[str] = None,
    ):
        self.root: Path = Path(project_root).resolve()
        self.config_path: Optional[Path] = (
            Path(config_file) if config_file is not None else None
        )
        self.data_dir: Optional[str] = data_dir

    async def _load_tables(self, *names: str) -> Tuple[Any, ...]:
        cfg = load_config(
            self.root,
            self.config_path,
            {"output.base_dir": self.data_dir} if self.data_dir else {},
        )
        store = create_storage_from_config(cfg.output)
        tables = []
        for name in names:
            df = await load_table_from_storage(name=name, storage=store)
            tables.append(df)
        return tuple(tables)

    async def basic_search(
        self,
        query: str,
        streaming: bool = False,
    ) -> Union[Tuple[str, Any], AsyncGenerator[str, None]]:
        text_units, = await self._load_tables("text_units")
        config_obj = load_config(
            self.root,
            self.config_path,
            {"output.base_dir": self.data_dir} if self.data_dir else {},
        )

        if streaming:
            return basic_search_streaming(
                config=config_obj,
                text_units=text_units,
                query=query,
            )
        return await basic_search(
            config=config_obj,
            text_units=text_units,
            query=query,
        )

    async def local_search(
        self,
        query: str,
        community_level: int = 2,
        response_type: str = "Multiple Paragraphs",
        streaming: bool = False,
    ) -> Union[Tuple[str, Any], AsyncGenerator[str, None]]:
        entities, communities, community_reports, text_units, relationships = await self._load_tables(
            "entities", "communities", "community_reports", "text_units", "relationships"
        )
        try:
            covariates = (await self._load_tables("covariates"))[0]
        except Exception:
            covariates = None

        config_obj = load_config(
            self.root,
            self.config_path,
            {"output.base_dir": self.data_dir} if self.data_dir else {},
        )

        if streaming:
            return local_search_streaming(
                config=config_obj,
                entities=entities,
                communities=communities,
                community_reports=community_reports,
                text_units=text_units,
                relationships=relationships,
                covariates=covariates,
                community_level=community_level,
                response_type=response_type,
                query=query,
            )
        return await local_search(
            config=config_obj,
            entities=entities,
            communities=communities,
            community_reports=community_reports,
            text_units=text_units,
            relationships=relationships,
            covariates=covariates,
            community_level=community_level,
            response_type=response_type,
            query=query,
        )

    async def global_search(
        self,
        query: str,
        community_level: int = 2,
        dynamic_selection: bool = False,
        response_type: str = "Multiple Paragraphs",
        streaming: bool = False,
    ) -> Union[Tuple[str, Any], AsyncGenerator[str, None]]:
        entities, communities, community_reports = await self._load_tables(
            "entities", "communities", "community_reports"
        )

        config_obj = load_config(
            self.root,
            self.config_path,
            {"output.base_dir": self.data_dir} if self.data_dir else {},
        )

        if streaming:
            return global_search_streaming(
                config=config_obj,
                entities=entities,
                communities=communities,
                community_reports=community_reports,
                community_level=community_level,
                dynamic_community_selection=dynamic_selection,
                response_type=response_type,
                query=query,
            )
        return await global_search(
            config=config_obj,
            entities=entities,
            communities=communities,
            community_reports=community_reports,
            community_level=community_level,
            dynamic_community_selection=dynamic_selection,
            response_type=response_type,
            query=query,
        )

    async def drift_search(
        self,
        query: str,
        community_level: int = 2,
        response_type: str = "Multiple Paragraphs",
        streaming: bool = False,
    ) -> Union[Tuple[str, Any], AsyncGenerator[str, None]]:
        entities, communities, community_reports, text_units, relationships = await self._load_tables(
            "entities", "communities", "community_reports", "text_units", "relationships"
        )

        config_obj = load_config(
            self.root,
            self.config_path,
            {"output.base_dir": self.data_dir} if self.data_dir else {},
        )

        if streaming:
            return drift_search_streaming(
                config=config_obj,
                entities=entities,
                communities=communities,
                community_reports=community_reports,
                text_units=text_units,
                relationships=relationships,
                community_level=community_level,
                response_type=response_type,
                query=query,
            )
        return await drift_search(
            config=config_obj,
            entities=entities,
            communities=communities,
            community_reports=community_reports,
            text_units=text_units,
            relationships=relationships,
            community_level=community_level,
            response_type=response_type,
            query=query,
        )
