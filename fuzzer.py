import random
import json
import Simulator as sawo


class Fuzzer:
    def __init__(self):
        self.instructions = ["add", "addi", "sub", "mulu", "divu", "remu"]
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
    
    def __str_code_to_list(self, test, instruction_class):
        output = []
        for PC, instruction in enumerate(test):
            opcode = instruction.split(" ")[0].strip()
            if opcode == "addi": opcode = "add"
            registers = instruction[instruction.find(" "):].split(",")
            destination_register = (registers[0].strip())
            operand_1 = (registers[1].strip())
            operand_2 = (registers[2].strip())
            output.append(instruction_class(PC, opcode, destination_register, operand_1, operand_2))
        return output

    def test(self, sim1, sim2, n=10, max_length=20):
        tests = self.generate_tests(n, max_length)
        errors = []
        for test in tests:
            res1 = sim1.start(self.__str_code_to_list(test, sawo.Instruction))
            res2 = sim2.start(self.__str_code_to_list(test, custom.Instruction))
            if json.dumps(res1, sort_keys=True) != json.dumps(res2, sort_keys=True):
                print("Mismatch found")
                errors.append((test, res1, res2))
        return errors


fuzzer = Fuzzer()
sim1 = sawo.CPU()

errors = fuzzer.test(sim1, sim2, 2000, 2000)
for i, error in enumerate(errors):
    with open(f"errors/code_error_{i}_1.json", "w") as file:
        json.dump(error[0], file, indent=2)
    with open(f"errors/error_{i}_1.json", "w") as file:
        json.dump(error[1], file, indent=2)
    with open(f"errors/error_{i}_2.json", "w") as file:
        json.dump(error[2], file, indent=2)


