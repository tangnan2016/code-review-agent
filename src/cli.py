"""命令行接口cli.py"""
import asyncio
import sys

import click

from src.main import run_review
from src.utils.logger import logger


@click.command()
@click.argument("source")
@click.option(
    "--provider", "-p",
    type=click.Choice(["openai", "deepsek", "claude", "ollama"], case_sensitive=False),
    default=None,
    help="LLM 提供者",
)
@click.option(
    "--model", "-m",
    default=None,
    help="模型名称",
)
@click.option(
    "--output", "-o",
    default=None,
    help="输出目录路径",
)
@click.option(
    "--format", "-f", "output_format",
    type=click.Choice(["html", "markdown", "json"], case_sensitive=False),
    default=None,
    help="输出格式",
)
@click.option(
    "--language", "-l",
    type=click.Choice(["zh", "en"], case_sensitive=False),
    default=None,
    help="报告语言",
)
@click.option(
    "--config", "-c",
    default="config/config.yaml",
    help="配置文件路径",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="显示详细日志",
)
def main(source, provider, model, output, output_format, language, config, verbose):
    """AI 代码评审工具

    SOURCE 可以是文件路径、目录路径或 Git 仓库地址
    """
    try:
        result = asyncio.run(
            run_review(
                source=source,
                provider=provider,
                model=model,
                output_dir=output,
                output_format=output_format,
                language=language,
                config_path=config,
                verbose=verbose,
            )
        )
        if result:
            click.echo(f"\n✅ 评审完成！报告已生成: {result}")
        else:
            click.echo("\n⚠️ 未找到可审查的代码文件")

    except KeyboardInterrupt:
        click.echo("\n已取消")
        sys.exit(130)
    except Exception as e:
        logger.error(f"评审失败: {e}")
        if verbose:
            raise
        sys.exit(1)


if __name__ == "__main__":
    main()