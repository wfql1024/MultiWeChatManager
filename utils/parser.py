from typing import Optional


class Logic2DictParser:
    def __init__(self, text):
        self.text = text.replace(" ", "")
        self.pos = 0
        self.length = len(self.text)

    def peek(self) -> Optional[str]:
        if self.pos < self.length:
            return self.text[self.pos]
        return None

    def consume(self, char=None) -> Optional[str]:
        if char and self.peek() != char:
            raise ValueError(f"Expected '{char}' at pos {self.pos}")
        current = self.peek()
        self.pos += 1
        return current

    def parse(self) -> dict:
        result = self.parse_expr()
        if self.peek() is not None:
            raise ValueError(f"Unexpected character at pos {self.pos}")
        return result

    def parse_expr(self) -> dict:
        # expr = term ( + term )*
        terms = [self.parse_term()]
        while self.peek() == '+':
            self.consume('+')
            terms.append(self.parse_term())
        if len(terms) == 1:
            return terms[0]
        else:
            return {"OR": terms}

    def parse_term(self) -> dict:
        # term = factor+
        factors = [self.parse_factor()]
        while True:
            c = self.peek()
            # factor start: '(', '!' or letter (variable)
            if c and (c.isalpha() or c == '!' or c == '('):
                factors.append(self.parse_factor())
            else:
                break
        if len(factors) == 1:
            return factors[0]
        else:
            # AND = merge dicts
            combined = {}
            for f in factors:
                if not isinstance(f, dict):
                    raise ValueError("Factor must be dict")
                combined.update(f)
            return combined

    def parse_factor(self) -> dict:
        # factor = '!' factor | '(' expr ')' | variable
        c = self.peek()
        if c == '!':
            self.consume('!')
            f = self.parse_factor()
            # 把key都取反
            return {("!" + k if not k.startswith("!") else k[1:]): v for k, v in f.items()}
        elif c == '(':
            self.consume('(')
            e = self.parse_expr()
            self.consume(')')
            return e
        elif c is not None and c.isalpha():
            var = self.consume()
            return {var: True}
        else:
            raise ValueError(f"Unexpected char '{c}' at pos {self.pos}")


# 测试例子
if __name__ == "__main__":
    tests = [
        "A",
        "!A",
        "A+B",
        "AB",
        "(A+B)C",
        "(A+B)(C+D)",
        "A+BC",
        "!(A+B)C",
        "A+!B+(!C!D)",
    ]
    for t in tests:
        print(f"{t} -> {Logic2DictParser(t).parse()}")
