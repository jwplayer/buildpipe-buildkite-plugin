import argparse

from buildpipe import pipeline


def create_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--infile', '-i', default='buildpipe.yml', metavar='FILE', help='Configuration file')
    parser.add_argument('--outfile', '-o', default='pipeline.yml', help='File for uploading to Buildkite')
    parser.add_argument('--dry-run', action='store_true', help='Validate infile')
    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()
    pipeline.create_pipeline(**vars(args))
