import random
import json


class Fuzzer:
    def __init__(self):
        self.instructions = ["add", "addi", "sub", "mul", "divu", "remu"]
        self.registers = [f"x{i}" for i in range(32)]

    def generate_tests(self, n, max_length):
        tests = []
        for _ in range(n):
            code = []
            length = random.randint(0, max_length)
            for _ in range(length):
                instruction = random.choice(self.instructions)
                dest = random.choice(self.registers)
                first_op = random.choice(self.registers)
                second_op = 0
                if instruction == "addi":
                    second_op = random.randint(1, 30)
                else:
                    second_op = random.choice(self.registers)
                code.append(f"{instruction} {dest}, {first_op}, {second_op}")
            tests.append(code)
        return tests

    def test(self, sim1, sim2, n=10, max_length=20):
        tests = self.generate_tests(n, max_length)
        errors = []
        for test in tests:
            res1 = sim1.start(test)
            res2 = sim2.start(test)
            if json.dumps(res1, sort_keys=True) != json.dumps(res2, sort_keys=True):
                print("Mismatch found")
                errors.append((test, res1, res2))
        return errors


