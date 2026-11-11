"""Call the existing host gate, retaining its refusal rather than bypassing it."""
import json
from perf.runner.host import host_record, quiet_machine_check


def main():
    record = host_record()
    verdict = quiet_machine_check()
    print(json.dumps({'host': record, 'quiet_machine_check': verdict}, indent=2))
    if not verdict['quiet']:
        raise SystemExit('host check refused; do not start browser runners')


if __name__ == '__main__':
    main()
