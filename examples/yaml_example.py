import io
import yaml

doc = """
foo: &anchor
  K1: One
  K2: Two

bar: *anchor

fix:
  type: 'FIX'
  major: '4'
  minor: '0'
  servicepack: '0'

  fields:
    f1:
      number: 8
      type: CHAR
    f2:
      number: 9
      type: 'INT'
    f3:
      number: 9
      type: 'INT'
    f4:
      number: 9
      type: 'INT'
    f5:
      number: 9
      type: 'INT'

  components:
    &c1
      -
        ? f3
        :
            required: true
      -
        ? f4
        :
            required: false

  messages:
    m1:
      - f1:
        required: true
      - f2:
        required: true
      *c1
      - f5:
        required: false
      - f6:
      - f7:
"""

result = yaml.load(io.StringIO(doc), Loader=yaml.FullLoader)
print(result)

doc2 = """
sitelist: &sites
  ? www.foo.com
  ? www.bar.com

anotherlist:
  << : *sites    # merge *sites into this mapping
  ? www.baz.com
  : something
"""

result = yaml.load(io.StringIO(doc2), Loader=yaml.FullLoader)
print(result)


inp = """\
- &CENTER {x: 1, y: 2}
- &LEFT {x: 0, y: 2}
- &BIG {r: 10}
- &SMALL {r: 1}
# All the following maps are equal:
# Explicit keys
- x: 1
  y: 2
  r: 10
  label: center/big
# Merge one map
- <<: *CENTER
  r: 10
  label: center/big
# Merge multiple maps
- <<: [*CENTER, *BIG]
  label: center/big
# Override
- <<: [*BIG, *LEFT, *SMALL]
  x: 1
  label: center/big
"""
result = yaml.load(io.StringIO(inp), Loader=yaml.FullLoader)
print(result)
